import yaml
import argparse
import codecs
from ExecStateFuzzer.subprocess_execution import execute_binary

parser = argparse.ArgumentParser()
parser.add_argument('input', type=str)
args = parser.parse_args()


input_data = codecs.decode(args.input, 'unicode_escape').encode('latin-1')

run_config = yaml.safe_load(open("config.yaml"))

try:
    result = execute_binary(input_data, run_config)
    print(result.model_dump_json(indent=1))

except Exception as e:
    print(str(e))