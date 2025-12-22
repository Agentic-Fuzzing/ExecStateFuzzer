import hashlib
import json
import random
import importlib.util
import sys
from pathlib import Path
from typing import List, Set, Tuple, Dict, Optional
import importlib

from .utils import eval_predicate_expression


class MutationEngine:    
    def __init__(self, operators_file: str, strategy_file: str):
        self.operators_file = Path(operators_file).resolve()
        self.strategy_file = Path(strategy_file).resolve()
        self.operators_module = None
        self.operators: Dict[str, callable] = {}
        self.rules: List[dict] = []
        self.mutation_history: Set[bytes] = set()
        self.max_mutation_history_size = 1000
        self.max_retries = 5

        self._load_operators()
        self._load_strategy()
    
    def _load_operators(self):
        if not self.operators_file.exists():
            raise FileNotFoundError(f"Operators file not found: {self.operators_file}")
        
        module_name = f"operators_{id(self)}"
        spec = importlib.util.spec_from_file_location(module_name, self.operators_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to load operators from {self.operators_file}")
        
        self.operators_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = self.operators_module
        spec.loader.exec_module(self.operators_module)
        
        self.operators = {}
        for name in dir(self.operators_module):
            if name.startswith('_'):
                continue
            obj = getattr(self.operators_module, name)
            if callable(obj):
                # Check signature - should accept (data: str, mutation_context: dict)
                import inspect
                sig = inspect.signature(obj)
                params = list(sig.parameters.values())
                if len(params) >= 2:
                    self.operators[name] = obj
    
    def _load_strategy(self):
        if not self.strategy_file.exists():
            raise FileNotFoundError(f"Strategy file not found: {self.strategy_file}")
        
        with open(self.strategy_file, 'r') as f:
            data = json.load(f)
        
        self.rules = data.get('rules', [])
        
        # Validate rules
        for rule in self.rules:
            if 'operators' not in rule:
                raise ValueError(f"Rule '{rule.get('name', 'unknown')}' missing 'operators' field")
            if not isinstance(rule['operators'], list):
                raise ValueError(f"Rule '{rule.get('name', 'unknown')}' operators must be a list")
            for op_entry in rule['operators']:
                if not isinstance(op_entry, list) or len(op_entry) != 2:
                    raise ValueError(f"Rule '{rule.get('name', 'unknown')}' operator entry must be [name, weight]")
                op_name, weight = op_entry
                if op_name not in self.operators:
                    raise ValueError(f"Rule '{rule.get('name', 'unknown')}' references unknown operator '{op_name}'")
                if not isinstance(weight, (int, float)) or weight <= 0:
                    raise ValueError(f"Rule '{rule.get('name', 'unknown')}' operator '{op_name}' has invalid weight")
    
    def reload(self):
        self._load_operators()
        self._load_strategy()
    
    def select_rule(self, mutation_context: dict) -> Optional[dict]:
        for rule in self.rules:
            condition = rule.get('condition')
            if condition is None:
                # Null condition means always match
                return rule
            if eval_predicate_expression(condition, mutation_context):
                return rule
        
        return None
    
    def select_operator(self, rule: dict) -> str:
        operators = rule['operators']
        names = [op[0] for op in operators]
        weights = [op[1] for op in operators]
        
        selected = random.choices(names, weights=weights)[0]
        return selected
    
    def mutate(self, data: bytes, mutation_context: dict, num_mutations: int) -> List[Tuple[bytes, str]]:
        if not self.operators:
            raise ValueError("No operators loaded")
        if not self.rules:
            raise ValueError("No rules defined in strategy")
        
        mutations = []
        for _ in range(num_mutations):
            # Select matching rule
            rule = self.select_rule(mutation_context)
            if rule is None:
                raise ValueError(f"No matching rule for mutation context: {mutation_context}")
            
            # Select operator from rule
            op_name = self.select_operator(rule)
            
            # Get operator function
            op_func = self.operators[op_name]
            
            # Execute mutation
            try:
                for _ in range(self.max_retries):
                    data_str = data.decode('latin-1')
                    mutated_str = op_func(data_str, mutation_context)
                    mutated_data = mutated_str.encode('latin-1')
                    m_hash = hashlib.md5(mutated_data).digest()
                    if m_hash not in self.mutation_history:
                        self.mutation_history.add(m_hash)
                        mutations.append((mutated_data, op_name))
                        break
            except Exception as e:
                raise RuntimeError(f"Operator '{op_name}' failed: {type(e).__name__}: {e}")
            
            if len(self.mutation_history) >= self.max_mutation_history_size:
                self.mutation_history.pop()
        
        return mutations

