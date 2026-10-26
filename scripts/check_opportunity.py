"""Arithmetic checks of matched-stratum summaries and exact sampling decisions.
"""
import csv, json, math
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
rows = list(csv.DictReader((HERE / 'data/matched_strata.csv').open(encoding='utf-8')))
assert len(rows) == 6 and sum(int(x['n']) for x in rows) == 1200
for x in rows:
    assert int(x['bin3_n']) + int(x['bin4_n']) == int(x['n'])
    delta = float(x['bpf_ms']) - float(x['selfront_ms'])
    assert abs(delta - (float(x['host_saved_ms']) - float(x['scheduler_ms']))) < 1e-10
    assert min(float(x[k]) for k in ['bpf_recall','selfront_recall','shuffled_recall']) > .96
    assert abs(float(x['bpf_recall']) - float(x['selfront_recall'])) <= .00200001
    for k in ['bpf_recall','selfront_recall','shuffled_recall']:
        assert abs(float(x[k])*200*10*5 - round(float(x[k])*200*10*5)) < 1e-8

# Check a compatible allocation of the aggregate remainder.
# Preserve precise cohort recalls behind six-decimal published bin4 values.
def q(v): return F(str(v))
N=3200
total_cost={'bpf':[q('.3'),q('.3'),q('.72'),q('1.62'),q('.30375'),F(0)],
            'selfront':[q('.3'),q('.3'),q('.54'),q('1.12'),q('.206875'),q('.18')]}
total_recall={'bpf':q('.9638125'),'selfront':q('.96225')}
bins={3:dict(n=1400,bpf_ms=q('4.2'),selfront_ms=q('3.35'),bpf_recall=q('.958'),selfront_recall=q('.956'),correlation=[1090,290,20]),
      4:dict(n=1800,bpf_ms=q('2.5'),selfront_ms=q('2.1'),correlation=[1250,500,50])}
for m in total_recall:
    bins[4][m+'_recall']=(N*total_recall[m]-1400*bins[3][m+'_recall'])/1800
    assert sum(bins[b]['n']*bins[b][m+'_ms'] for b in bins)/N == sum(total_cost[m])
assert [sum(bins[b]['correlation'][i] for b in bins) for i in range(3)] == [2340,790,70]
for b in bins:
    assert sum(bins[b]['correlation'])==bins[b]['n']
    assert all(0<=x<=lim for x,lim in zip(bins[b]['correlation'],[1250,625,625]))

cell_cost=[]
for x in rows:
    B=[q('.3'),q('.3')]+[(q(x['bpf_ms'])-q('.6'))*v/sum(total_cost['bpf'][2:5]) for v in total_cost['bpf'][2:5]]+[F(0)]
    saved=q(x['host_saved_ms'])
    savings_weights=[total_cost['bpf'][i]-total_cost['selfront'][i] for i in range(2,5)]
    S=B[:2]+[B[i]-saved*savings_weights[i-2]/sum(savings_weights) for i in range(2,5)]+[q(x['scheduler_ms'])]
    assert sum(B)==q(x['bpf_ms']) and sum(S)==q(x['selfront_ms']) and min(S)>=0
    cell_cost.append({'bpf':B,'selfront':S})

components=['preparation','pilot','adjacency_scan','vector_work','queue','scheduler']
witness=[]
for b,base in bins.items():
    residual_n=base['n']-600
    corr=[x-y for x,y in zip(base['correlation'],[480,108,12])]
    assert min(corr)>=0 and sum(corr)==residual_n
    for m in total_cost:
        # Uniform common costs/scheduler by bin, split remaining host work in
        # the same ratios as the existing full-cohort cost categories.
        glob=total_cost[m]
        scale=(base[m+'_ms']-glob[0]-glob[1]-glob[5])/sum(glob[2:5])
        whole=glob[:2]+[v*scale for v in glob[2:5]]+[glob[5]]
        selected=[sum(100*c[m][i] for c in cell_cost) for i in range(6)]
        remainder=[(base['n']*whole[i]-selected[i])/residual_n for i in range(6)]
        latency=(base['n']*base[m+'_ms']-sum(100*q(x[m+'_ms']) for x in rows))/residual_n
        recall=(base['n']*base[m+'_recall']-sum(100*q(x[m+'_recall']) for x in rows))/residual_n
        assert min(remainder)>=0 and sum(remainder)==latency and q('.95')<recall<=1
        witness.append(dict(bin=b,method=m,n=residual_n,mean_ms=float(latency),recall=float(recall),positive=corr[0],weak=corr[1],adverse=corr[2],**{k:float(v) for k,v in zip(components,remainder)}))
for m in total_cost:
    for i,k in enumerate(components):
        recovered=(sum(200*c[m][i] for c in cell_cost)+sum(q(str(z[k]))*z['n'] for z in witness if z['method']==m))/3200
        assert abs(float(recovered-total_cost[m][i]))<1e-12
pooled=[]
for m in total_cost:
    zs=[z for z in witness if z['method']==m]
    pooled.append(dict(method=m,n=2000,**{k:sum(z[k]*z['n'] for z in zs)/2000 for k in ['mean_ms','recall']+components}))
payload=dict(status='PASS',scope='aggregate compatibility allocation',matched_per_cell_correlation=[160,36,4],matched_per_cell_per_bin_correlation=[80,18,2],original_bin_correlation={b:bins[b]['correlation'] for b in bins},residual_bins=witness,residual_pooled=pooled,shuffled_residual=dict(n=2000,mean_ms=float((3200*q('3.260')-sum(200*q(x['shuffled_ms']) for x in rows))/2000),recall=float((3200*q('.9612')-sum(200*q(x['shuffled_recall']) for x in rows))/2000)))
(HERE/'outputs/subset_compatibility.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
print(json.dumps(payload,indent=2))

def distribution(U, Y, s=8, d=32):
    out=[]
    for y in range(s+1):
        for z in range(s-y+1):
            t=s-y-z
            p=F(math.factorial(s),math.factorial(y)*math.factorial(z)*math.factorial(t))*F(Y,d)**y*F(U-Y,d)**z*F(d-U,d)**t
            score=F(d*y,s)/(2+d+10*F(d*(y+z),s))
            out.append((score,p))
    assert sum(p for _,p in out)==1
    return out

states=[dict(name='depleted',d=32,A=16,U=6,Y=2),dict(name='productive',d=32,A=16,U=14,Y=10)]
rates=[F(z['Y'],2+z['d']+10*z['U']) for z in states]
out={'scope':'exact one-window enumeration; independent replacement samples; no query speed claim', 'samples':8,'profile':{'a':1,'b':10,'c':2}, 'states':states,'true_rates':[float(r) for r in rates], 'mean_depletion':float((F(14,16)+F(6,16))/2),'normalized_spread':float((max(rates)-min(rates))/max(rates)),'native_orders':[]}
dists=[distribution(z['U'],z['Y']) for z in states]
for native in [0,1]:
    prob=F(0)
    expected=F(0)
    for s0,p0 in dists[0]:
        for s1,p1 in dists[1]:
            pick=0 if s0>s1 else 1 if s1>s0 else native
            p=p0*p1
            prob+=p*(pick==1)
            expected+=p*rates[pick]
    out['native_orders'].append({'native':states[native]['name'],'native_gap':float((max(rates)-rates[native])/max(rates)),'probability_select_productive':float(prob),'expected_selected_true_rate':float(expected),'native_true_rate':float(rates[native]),'expected_local_rate_change':float(expected-rates[native])})
(HERE/'outputs/exact_window_check.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'aggregate_arithmetic':'PASS','cells':len(rows),'requests':1200,'exact_window':out},indent=2))
