"""Validate constructed finite tuning records; no ANN execution. Standard library only."""
import csv, json
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
grid=read(HERE/'data/host_tuning_grid.csv')
test=read(HERE/'data/host_selected_test.csv')
baseline=read(HERE/'data/host_composition.csv')
anchors={('Articles','FAVOR-A'):(512,'3.79',['1','1','.974','.982']),
         ('Articles','SelFront'):(512,'3.29',['1','1','.972','.982']),
         ('Media','FAVOR-A'):(1024,'8.94',['1','1','.968','.976']),
         ('Media','SelFront'):(1024,'8.58',['1','1','.966','.976'])}
for key,(width,ms,rs) in anchors.items():
    anchor=next(r for r in baseline if (r['collection'],r['variant'])==key)
    assert int(anchor['E'])==width and D(anchor['mean_ms'])==D(ms)
    assert all(D(anchor[f'recall_bin{i}'])==D(rs[i-1]) for i in range(1,5))
widths={'Articles':[256,384,512],'Media':[512,768,1024]}
targets={'Articles':D('.9880'),'Media':D('.9855')}
def recall(r): return sum(D(r[f'recall_bin{i}']) for i in range(1,5))/4
def minimum(r): return min(D(r[f'recall_bin{i}']) for i in range(1,5))
assert len(grid)==12 and len(test)==4
for r in grid+test:
    assert D(r['target'])==targets[r['collection']] and D(r['g'])==D('.01')
    assert all(D(0)<=D(r[f'recall_bin{i}'])<=D(1) for i in range(1,5))
    assert D(r['recall_bin1'])==D(r['recall_bin2'])==1
    assert minimum(r)>=D('.95')
    phase='tuning' if 'tuning_ms' in r else 'test'
    assert int(r[phase+'_requests'])==(2000 if phase=='tuning' else 10000)
    assert 4*int(r['bin_requests'])==int(r[phase+'_requests'])
    assert D(r[phase+'_ms'])>0
    # Means over five repetitions and recall@10 admit these finite denominators.
    for i in range(1,5):
        hits=D(r[f'recall_bin{i}'])*int(r['bin_requests'])*10*5
        assert hits==hits.to_integral_value()
selected=[]
for collection in widths:
    for variant in ['FAVOR-A','SelFront']:
        candidates=[r for r in grid if (r['collection'],r['variant'])==(collection,variant)]
        assert sorted(int(r['width']) for r in candidates)==widths[collection]
        feasible=[r for r in candidates if recall(r)>=targets[collection] and minimum(r)>=D('.95')]
        chosen=min(feasible,key=lambda r:(D(r['tuning_ms']),int(r['width'])))
        matches=[r for r in test if (r['collection'],r['variant'])==(collection,variant)]
        assert len(matches)==1
        t=matches[0]
        assert chosen['width']==t['width']
        # Test quality is reported, not used to select or change the chosen point.
        anchor=next(r for r in baseline if (r['collection'],r['variant'])==(collection,variant))
        if t['width']==anchor['E']:
            assert D(t['test_ms'])==D(anchor['mean_ms'])
            assert all(D(t[f'recall_bin{i}'])==D(anchor[f'recall_bin{i}']) for i in range(1,5))
        selected.append(dict(collection=collection,variant=variant,width=int(t['width']),tuning_ms=chosen['tuning_ms'],tuning_recall=str(recall(chosen)),test_ms=t['test_ms'],test_recall=str(recall(t)),test_min_bin=str(minimum(t)),test_target_met=recall(t)>=targets[collection],existing_test_anchor_preserved=t['width']==anchor['E']))
comparisons=[]
for collection in widths:
    b=next(r for r in selected if r['collection']==collection and r['variant']=='FAVOR-A')
    s=next(r for r in selected if r['collection']==collection and r['variant']=='SelFront')
    comparisons.append(dict(collection=collection,baseline_name='FAVOR-A',favor_minus_selfront_ms=str(D(b['test_ms'])-D(s['test_ms'])),selfront_reduction_percent=str(100*(D(b['test_ms'])-D(s['test_ms']))/D(b['test_ms'])),selfront_minus_favor_recall=str(D(s['test_recall'])-D(b['test_recall']))))
out=dict(status='PASS',scope='Arithmetic and finite selection on constructed aggregate records; not a benchmark',candidates=12,selected=selected,comparisons=comparisons)
(HERE/'outputs/host_tuning_checks.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
