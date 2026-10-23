"""Analyze archived paper summaries; no graph benchmark is executed."""
import csv
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name):
    with (ROOT/'data'/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
summary=[]
for r in read('main.csv'):
    summary.append(dict(collection=r['collection'],graph_reduction_percent=100*(1-float(r['selfront_graph_ms'])/float(r['bpf_graph_ms'])),all_reduction_percent=100*(1-float(r['selfront_all_ms'])/float(r['bpf_all_ms']))))
out=ROOT/'outputs';out.mkdir(exist_ok=True)
(out/'archive_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
