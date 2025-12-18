import random

def insert_random_bytes(input_str: str, state_dict: dict) -> str:
    return input_str + random.randbytes(2).decode('latin-1')