"""Actual finite-state arithmetic, not an ANN robustness benchmark."""
import json, math
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"outputs"
def samples(U,Y):
    out=[]
    for y in range(9):
        for z in range(9-y):
            t=8-y-z
            p=F(math.factorial(8),math.factorial(y)*math.factorial(z)*math.factorial(t))*F(Y,32)**y*F(U-Y,32)**z*F(32-U,32)**t
            out.append((4*y,4*(y+z),p))
    assert sum(p for _,_,p in out)==1
    return out
states=[(4,2),(16,5)] # (U,Y), same degree 32; candidate 0 is native-first.
true=[F(Y,34+10*U) for U,Y in states]
dist=[samples(*s) for s in states]
rows=[]
for rho,kappa in [(5,2),(10,2),(20,2),(10,0),(10,4)]:
    rates=[F(Y,32+kappa+rho*U) for U,Y in states]
    winner=0 if rates[0]>=rates[1] else 1
    p0=F(0)
    for y0,u0,a in dist[0]:
        for y1,u1,b in dist[1]:
            p0+=a*b*(F(y0,32+kappa+rho*u0)>=F(y1,32+kappa+rho*u1))
    expected=p0*true[0]+(1-p0)*true[1]
    rows.append(dict(rho=rho,kappa=kappa,exact_count_choice=winner,probability_select_true_best=float(p0),expected_true_rate=float(expected),relative_local_regret=float(1-expected/max(true)),exact_count_relative_regret=float(1-true[winner]/max(true))))
# Previous wide-gap R012 states: productive state remains the rate winner over
# the rectangle rho in [5,20], kappa in [0,4]; affine inequality corners suffice.
for rho in [5,20]:
    for kappa in [0,4]:
        assert F(10,32+kappa+rho*14)>F(2,32+kappa+rho*6)
out=dict(scope='exact one-window sensitivity at fixed evaluation profile rho=10,kappa=2; independent replacement s=8; native wins ties',degree=32,states_U_Y=states,true_rates=[float(x) for x in true],crossing='rho = 8 + kappa/4',rows=rows,wide_gap_rectangle_check='PASS')
(HERE/'profile_mismatch.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
