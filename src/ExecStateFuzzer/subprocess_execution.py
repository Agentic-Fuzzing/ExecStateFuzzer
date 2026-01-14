import os
import subprocess
import time

from ExecStateFuzzer.utils import coerce_value_to_int, eval_predicate_expression

from .models import ExecutionOutcome
from pydantic import BaseModel
from typing import Optional

class BinaryExecutionResult(BaseModel):
    input_data: bytes
    execution_outcome: ExecutionOutcome
    execution_time: float
    crash_info: Optional[str]
    execution_state: tuple
    mutation_context: dict
    stdout: Optional[str]


def _compute_state_dict(spec: list, execution_value_samples: dict, latest_values: dict, show_execution_values: bool) -> dict:
    result = {}
    for item in spec:
        item_type = item['type']
        if item_type == 'value':
            name = item['name']
            if name in latest_values:
                result[name] = latest_values[name]
        elif item_type == 'sum':
            name = item['name']
            values = execution_value_samples.get(name, [])
            total = 0
            for v in values:
                total += coerce_value_to_int(v)
            result[name] = total
        elif item_type == 'predicate':
            expr = item['expr']
            fired = eval_predicate_expression(expr, latest_values)
            if show_execution_values:
                try:
                    print(f"PRED env: {latest_values}")
                    print(f"PRED expr: {expr} -> {fired}")
                except Exception:
                    pass
            result[expr] = 1 if fired else 0
        elif item_type == 'counter':
            expr = item['expr']
            count = 0
            max_length = max((len(values) for values in execution_value_samples.values()), default=0)
            
            for i in range(max_length):
                step_values = {}
                for name, values in execution_value_samples.items():
                    if i < len(values):
                        step_values[name] = values[i]
                
                if eval_predicate_expression(expr, step_values):
                    count += 1
            
            if show_execution_values:
                try:
                    print(f"COUNTER expr: {expr} -> {count} times")
                except Exception:
                    pass
            result[expr] = count
        elif item_type == 'set':
            name = item['name']
            values = execution_value_samples.get(name, [])

            unique_values = set()
            for v in values:
                if isinstance(v, (bytes, bytearray)):
                    unique_values.add(v)
                elif isinstance(v, int):
                    unique_values.add(v)
                else:
                    unique_values.add(str(v))
            
            if show_execution_values:
                try:
                    print(f"SET {name}: {tuple(sorted(unique_values))}")
                except Exception:
                    pass
            result[name] = tuple(sorted(unique_values))
    
    return result


def _dict_to_state_tuple(spec: list, state_dict: dict) -> tuple:
    computed = []
    for item in spec:
        item_type = item['type']
        if item_type == 'value':
            name = item['name']
            if name in state_dict:
                computed.append(f"{name} (value)")
                computed.append(state_dict[name])
        elif item_type == 'sum':
            name = item['name']
            if name in state_dict:
                computed.append(f"{name} (sum)")
                computed.append(state_dict[name])
        elif item_type == 'predicate':
            expr = item['expr']
            if expr in state_dict:
                computed.append(expr)
                computed.append(state_dict[expr])
        elif item_type == 'counter':
            expr = item['expr']
            if expr in state_dict:
                computed.append(f"{expr} (count)")
                computed.append(state_dict[expr])
        elif item_type == 'set':
            name = item['name']
            if name in state_dict:
                computed.append(f"{name} (set)")
                computed.append(state_dict[name])
    
    return tuple(computed)

def execute_binary(input_data: bytes, run_config: dict, show_execution_values: bool = False) -> BinaryExecutionResult:
    TARGET_BIN = run_config['target']['binary_path']
    PER_RUN_TIMEOUT = run_config['fuzzer']['per_run_timeout']
    execution_values_list = run_config['fuzzer'].get('execution_values') or []
    EXECUTION_VALUES_DICT = {item['name']: item for item in execution_values_list}
    
    stdout = None
    execution_time = 0
    execution_value_samples: dict = {}
    
    try:
        arch = os.uname().machine
        cmd = ["setarch", arch, "-R", TARGET_BIN]
        start = time.perf_counter()
        result = subprocess.run(cmd, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=PER_RUN_TIMEOUT)
        end = time.perf_counter()
        stdout = result.stdout
        execution_time = end - start
    except Exception as e:
        print(f"Error running binary with {input_data}: {e}")
        crash_info = str(e)
        return BinaryExecutionResult(
            input_data=input_data,
            execution_outcome=ExecutionOutcome.CRASH,
            execution_time=0,
            crash_info=crash_info,
            execution_state=(),
            mutation_context={},
            stdout=stdout
        )
    
    stdout_text = stdout.decode('latin-1')
    for line in stdout_text.splitlines():
        line = line.strip()
        # Look for "name: value" patterns anywhere in the line
        for exec_name in EXECUTION_VALUES_DICT.keys():
            pattern = f"{exec_name}:"
            if pattern in line:
                idx = line.find(pattern)
                value_part = line[idx + len(pattern):].strip()

                value_str = value_part.split()[0] if value_part.split() else value_part

                exec_value_def = EXECUTION_VALUES_DICT[exec_name]
                value_type = exec_value_def.get('type', 'string')

                try:
                    if value_type == 'int':
                        value = int(value_str)
                    elif value_type == 'float':
                        value = float(value_str)
                    elif value_type == 'bool':
                        value = int(value_str) if value_str.isdigit() else (1 if value_str.lower() in ('true', 'yes', '1') else 0)
                    else:
                        value = value_str

                    if exec_name not in execution_value_samples:
                        execution_value_samples[exec_name] = []
                    execution_value_samples[exec_name].append(value)
                except (ValueError, TypeError, IndexError):
                    pass
    
    if show_execution_values:
        for name, values in execution_value_samples.items():
            print(f"{name}: {values}")
    
    latest_values = {k: v_list[-1] for k, v_list in execution_value_samples.items() if v_list}

    state_spec = run_config['fuzzer'].get('execution_state') or []
    computed_state_dict = _compute_state_dict(state_spec, execution_value_samples, latest_values, show_execution_values)
    computed_state = _dict_to_state_tuple(state_spec, computed_state_dict)

    mutation_context_spec = run_config['fuzzer'].get('mutation_context') or []
    computed_mutation_context = _compute_state_dict(mutation_context_spec, execution_value_samples, latest_values, show_execution_values)

    return BinaryExecutionResult(
        input_data=input_data,
        execution_outcome=ExecutionOutcome.NORMAL,
        execution_time=execution_time,
        crash_info=None,
        execution_state=computed_state,
        mutation_context=computed_mutation_context,
        stdout=stdout
    )