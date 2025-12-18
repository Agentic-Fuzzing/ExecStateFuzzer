import hashlib
import random
from functools import wraps

MUTATION_HISTORY = set()
MAX_HISTORY_SIZE = 1000

def ensure_unique(max_retries=5):
    def decorator(func):
        @wraps(func)
        def wrapper(input_str: str, state_dict: dict, *args, **kwargs) -> str:
            for _ in range(max_retries):
                mutated = func(input_str, state_dict, *args, **kwargs)
                m_hash = hashlib.md5(mutated.encode('latin-1')).digest()
                
                if m_hash not in MUTATION_HISTORY:
                    # Maintain cache size
                    if len(MUTATION_HISTORY) > MAX_HISTORY_SIZE:
                        MUTATION_HISTORY.pop() 
                    MUTATION_HISTORY.add(m_hash)
                    return mutated
            
            return mutated + random.randbytes(2).decode('latin-1')
        return wrapper
    return decorator

@ensure_unique()
def insert_random_bytes(input_str: str, state_dict: dict) -> str:
    return input_str + random.randbytes(2).decode('latin-1')