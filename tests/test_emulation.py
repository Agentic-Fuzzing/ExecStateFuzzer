import yaml
import argparse
import codecs
from ExecStateFuzzer.ql_emulation import execute_with_qiling

parser = argparse.ArgumentParser()
parser.add_argument('input', type=str)
args = parser.parse_args()


input_data = codecs.decode(args.input, 'unicode_escape').encode('latin-1')

run_config = yaml.safe_load(open("config.yaml"))

try:
    result = execute_with_qiling(input_data, run_config, force_stdout=True)

except Exception as e:
    print(str(e))