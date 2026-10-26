"""Check host-window behavior and the accompanying composition summaries."""
from pathlib import Path
import csv,json,sys,random,math
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from host_window import choose_expansion
from selfront import Config
cfg=Config(s=32,a=1,b=4,c=0)
adj=[list(range(2,34)),list(range(34,66))]
discovered=set(range(2,28))|set(range(34,50))
eligible=set(range(2,24))|set(range(28,30))|set(range(34,38))|set(range(50,62))
frontier=[(1.,0),(1.04,1)]
saved=(list(frontier),set(discovered),set(eligible))
def pick(**kw):return choose_expansion(frontier,adj,discovered,eligible,random.Random(7),cfg,**kw)
assert pick()==(1,64)
assert pick(enabled=False)==(0,0)
assert pick(completed_steps=3)==(0,0)
assert pick(host_stopped=True)==(None,0)
assert pick(expansion_bound=1.02)==(0,0)
# An eligible-fraction-dependent host can leave the worst-heap bound open.
assert pick(expansion_bound=math.inf)==(1,64)
assert saved==(frontier,discovered,eligible)
# Zero evidence uses native key and then ID, including a reverse input order.
assert choose_expansion(frontier[::-1],adj,set(range(66)),eligible,random.Random(7),cfg)==(0,64)
rows=list(csv.DictReader((ROOT/'data/host_composition.csv').open(encoding='utf-8')))
contrasts=list(csv.DictReader((ROOT/'data/host_contrasts.csv').open(encoding='utf-8')))
legacy={x['collection']:x for x in csv.DictReader((ROOT/'data/external.csv').open(encoding='utf-8'))}
summary=[]
for c in contrasts:
 group=[x for x in rows if x['collection']==c['collection']]
 assert len(group)==4
 for x in group:
  assert int(x['requests'])==10000
  assert min(float(x[f'recall_bin{i}']) for i in range(1,5))>=.95
 assert len({(x['E'],x['g']) for x in group})==1
 times={x['variant']:float(x['mean_ms']) for x in group}
 assert times['FAVOR-A']==float(legacy[c['collection']]['favor_ms'])
 delta=times['FAVOR-A']-times['SelFront'];assert abs(delta-float(c['mean_saving_ms']))<1e-12
 radius=2.7764451051977987*float(c['se_ms'])
 recalls={x['variant']:sum(float(x[f'recall_bin{i}']) for i in range(1,5))/4 for x in group}
 assert abs(recalls['FAVOR-A']-recalls['SelFront']-.0005)<1e-12
 assert recalls['FAVOR-A']==recalls['Eligible-first']
 assert abs(recalls['SelFront']-recalls['Shuffled-score']-.00025)<1e-12
 sr=next(x for x in group if x['variant']=='SelFront'); sh=next(x for x in group if x['variant']=='Shuffled-score')
 assert all(float(sr[f'recall_bin{i}'])>=float(sh[f'recall_bin{i}']) for i in range(1,5))
 summary.append(dict(collection=c['collection'],saving_percent=100*delta/times['FAVOR-A'],saving_ms=delta,interval95_ms=[delta-radius,delta+radius],mean_recalls=recalls,minimum_recalls={x['variant']:min(float(x[f'recall_bin{i}']) for i in range(1,5)) for x in group}))
(ROOT/'outputs/host_composition.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('Host stopping/bound/native-step/tie/read-only checks passed; 16 composition rows and four contrasts consistent.')
print(json.dumps(summary,indent=2))
