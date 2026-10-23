"""Analyze archived paired run-mean summaries; does not execute benchmarks."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# Two-sided .95 Student interval for five independent paired run means, df=4.
T4=2.7764451051977987
with (ROOT/'data/paired_contrasts.csv').open(newline='',encoding='utf-8') as f:
    records=list(csv.DictReader(f))
result=[]
for r in records:
    assert int(r['repetitions'])==5
    mean,se=float(r['mean_difference_ms']),float(r['se_run_mean_ms'])
    assert se>=0
    result.append(dict(collection=r['collection'],configuration=r['configuration'],comparison=r['comparison'],mean_difference_ms=mean,interval95_ms=[mean-T4*se,mean+T4*se]))
out=ROOT/'outputs/paired_contrasts.json';out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
