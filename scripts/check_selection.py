"""Recompute selection from archived finite-grid summaries; no ANN execution."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(name):
    with (ROOT/'data'/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def pool(row):
    n3,n4=int(row['bin3_requests']),int(row['bin4_requests'])
    assert abs((n3*float(row['bin3_recall'])+n4*float(row['bin4_recall']))/(n3+n4)-float(row['pooled_recall']))<1e-8
    return min(float(row['bin3_recall']),float(row['bin4_recall']))
grid=read('tuning_grid.csv')
for row in grid:
    minimum=pool(row)
    assert abs(minimum-float(row['min_bin_recall']))<1e-8
    assert int(row['tuning_graph_requests'])==int(row['bin3_requests'])+int(row['bin4_requests'])
chosen=[]
points=read('quality_points.csv')
for test in read('selected_test_bins.csv'):
    assert pool(test)>=.95
    feasible=[r for r in grid if r['collection']==test['collection'] and r['method']==test['method'] and float(r['pooled_recall'])>=float(test['target']) and pool(r)>=.95]
    selected=min(feasible,key=lambda r:(float(r['tuning_ms']),float(r['beta'])))
    assert float(selected['beta'])==float(test['beta'])
    original=next(r for r in points if r['collection']==test['collection'] and r['method']==test['method'] and float(r['target'])==float(test['target']))
    assert abs(float(original['test_recall'])-float(test['pooled_recall']))<=.00005001
    assert abs(float(original['tuning_recall'])-float(selected['pooled_recall']))<=.00005001
    assert float(original['test_ms'])==float(test['test_ms'])
    chosen.append(dict(collection=test['collection'],method=test['method'],target=float(test['target']),beta=float(selected['beta']),tuning_ms=float(selected['tuning_ms'])))
for row in read('sensitivity_quality.csv'):assert pool(row)>=.95
out=ROOT/'outputs/selection.json';out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(chosen,indent=2)+'\n',encoding='utf-8')
print(f'Validated {len(grid)} tuning rows, {len(chosen)} selected points, and six sensitivity quality records.')
