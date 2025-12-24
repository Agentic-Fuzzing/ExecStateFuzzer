import yaml
import codecs
from typing import Any, Tuple
from ExecStateFuzzer.ql_emulation import execute_with_qiling

run_config = yaml.safe_load(open("config.yaml"))

results = []
execution_state_set = set[Tuple[Any, ...]]()
for seed_value in run_config['fuzzer']['seed_inputs']:
    input_data = codecs.decode(seed_value, 'unicode_escape').encode('latin-1')

    result = execute_with_qiling(input_data, run_config)

    results.append({'seed': input_data, 'execution_state': result.execution_state})
    execution_state_set.add(result.execution_state)

print(f"Seed input execution states: {results}\n")
print(f"Execution state set (size={len(execution_state_set)}): {execution_state_set}")