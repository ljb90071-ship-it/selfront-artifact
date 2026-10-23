"""Run the small graph input and emit actual operator traces, not latency estimates."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.selfront import Config, search, squared_distance

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input', type=Path, default=ROOT/'examples/circle.json')
parser.add_argument('--config', type=Path, default=ROOT/'configs/operator.json')
parser.add_argument('--output', type=Path, default=ROOT/'outputs/example.json')
args = parser.parse_args()
data = json.loads(args.input.read_text(encoding='utf-8'))
data.pop('description', None)
cfg = Config(**json.loads(args.config.read_text(encoding='utf-8')))
truth = [v for _, v in sorted((squared_distance(data['vectors'][v], data['query']), v)
                              for v in data['eligible'])[:data['k']]]
out = {'exact_ids': truth, 'runs': {}}
for name, enabled in [('BPF', False), ('SelFront', True)]:
    result = search(**data, scheduler=enabled, cfg=cfg, trace=True)
    result['recall'] = len(set(truth) & set(result['ids'])) / len(truth) if truth else 1.0
    out['runs'][name] = result
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(out, indent=2)+'\n', encoding='utf-8')
print(json.dumps({name: {'recall': r['recall'], **r['counters']} for name, r in out['runs'].items()}, indent=2))
print('Trace:', args.output)
