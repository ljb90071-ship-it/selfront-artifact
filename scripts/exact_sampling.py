"""Exact one-decision sampling calculation, not an ANN performance experiment."""
from fractions import Fraction as F
from math import comb
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path

@lru_cache(None)
def distribution(d,u,y,s=8,a=1,b=4,c=0):
    assert 0<=y<=u<=d and a>0 and b>=0 and c>=0
    if d == 0:
        return {F(0): F(1)}
    if d<=s:
        return {F(y,c+a*d+b*u): F(1)}
    dist=defaultdict(F)
    for h in range(s+1):
        for j in range(s-h+1):
            # h: unseen eligible; j: unseen ineligible; s-h-j: visited
            p=F(comb(s,h)*comb(s-h,j)*y**h*(u-y)**j*(d-u)**(s-h-j),d**s)
            if p:
                score=F(d*h,s*(c+a*d)+b*d*(h+j))
                dist[score]+=p
    assert sum(dist.values())==1
    return dict(dist)

def mean(dist):return sum(v*p for v,p in dist.items())
def pair(first,second,s=8):
    # first is nearer and wins exact sampled-score ties.
    da,db=(distribution(*v,s) for v in (first,second))
    prob=sum(pa*pb for a,pa in da.items() for b,pb in db.items() if b>a)
    qa=F(first[2],first[0]+4*first[1]);qb=F(second[2],second[0]+4*second[1])
    achieved=qa*(1-prob)+qb*prob
    return {'s':s,'choose_second':float(prob),'true_scores':[float(qa),float(qb)],
            'mean_scores':[float(mean(da)),float(mean(db))],
            'expected_local_regret':float(max(qa,qb)-achieved)}

rows=[]
for u in range(1,33):
    for y in range(1,u+1):
        dist=distribution(32,u,y)
        expected=mean(dist); true=F(y,32+4*u)
        # Conditioning on K makes the denominator deterministic and
        # E[H|K]=K*y/u. Verify the one-binomial-sum expression independently.
        formula=F(y,u)*sum(F(comb(8,k)*u**k*(32-u)**(8-k),32**8)*F(k,8+4*k) for k in range(9))
        assert expected==formula and expected<=true
        rows.append((u,y,true,expected))
reversals=[]
for ua,ya,qa,ea in rows:
    for ub,yb,qb,eb in rows:
        if qa>qb and ea<eb:
            reversals.append((float((qa-qb)/qa),ua,ya,ub,yb,float(qa),float(qb),float(ea),float(eb)))
print('Conditional ratio mean identity and downward bias verified for 528 positive-yield states.')
for a,b,c in [(1,0,0),(1,1,0),(2,4,3)]:
    for u,y in [(0,0),(2,0),(2,2),(16,4),(32,16)]:
        expected=mean(distribution(32,u,y,8,a,b,c))
        truth=F(y,c+a*32+b*u)
        assert expected<=truth
        if b>0 and 0<u<32 and y>0: assert expected<truth
        else: assert expected==truth
assert mean(distribution(8,2,1,8))==F(1,16)
print('Zero yield, zero variable cost, all-unseen, positive fixed cost, and exact-count branches checked.')
print('Largest relative true-score reversal:',max(reversals))
examples={'wide':[(32,6,2),(32,16,12)], 'depleted':[(32,2,2),(32,16,4)]}
result={name:[pair(*vs,s) for s in (4,8,16,32)] for name,vs in examples.items()}
for name,values in result.items():print(name,json.dumps(values))
out=Path(__file__).resolve().parents[1]/'outputs'/'probe_results.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
