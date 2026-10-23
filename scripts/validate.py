"""Validate operator invariants and arithmetic relationships in archived tables."""
import csv
import json
import math
from pathlib import Path
import random
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.selfront import Config, probe, route, search
from src.favor_rules import adjusted_score, exclusion_distance, should_stop

def rows(name):
    with (ROOT/'data'/name).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))

class OperatorChecks(unittest.TestCase):
    def test_read_only_exact_and_empty_probes(self):
        d, s = {1}, {1,2}
        self.assertEqual(probe([], d, s, random.Random(0), Config()), (0,0,0,0))
        u,y,score,reads=probe([1,2,3],d,s,random.Random(0),Config())
        self.assertEqual((u,y,reads),(2,1,3))
        self.assertAlmostEqual(score,1/11)
        self.assertEqual((d,s),({1},{1,2}))

    def test_replacement_observations_are_not_deduplicated(self):
        class FixedPositions:
            def randrange(self, n): return 0
        self.assertEqual(probe(list(range(10)),set(),{0},FixedPositions(),Config(s=4)),(10,10,.2,4))

    def test_bridge_and_result_admission(self):
        # Vertex 1 is ineligible but is the only path to eligible vertex 2.
        r=search([[0],[1],[2]],[[1],[2],[]],{2},[2],0,k=1,ef=3)
        self.assertEqual(r['ids'],[2]); self.assertFalse(r['fallback'])
        # Eligible neighbor updates R even though its distance excludes it from W.
        r=search([[0],[10]],[[1],[]],{1},[0],0,k=1,ef=1)
        self.assertEqual(r['ids'],[1]); self.assertFalse(r['fallback'])

    def test_fallback_and_insufficient_cardinality(self):
        r=search([[0],[1],[2]],[[],[],[]],{1,2},[2],0,k=3,ef=1)
        self.assertEqual(r['ids'],[2,1]); self.assertTrue(r['fallback'])
        self.assertEqual(r['counters']['fallback_distances'],2)

    def test_native_stops_before_expanding_distant_candidate(self):
        r=search([[0],[10],[1],[2]],[[1,2],[3],[],[]],{0,1,2,3},[0],0,k=1,ef=2,trace=True)
        self.assertEqual([x['chosen'] for x in r['trace']],[0,2])
        self.assertEqual(r['counters']['graph_distances'],3)

    def test_gate_periodicity_and_reproducibility(self):
        args=json.loads((ROOT/'examples/circle.json').read_text())
        args.pop('description')
        a=search(**args,trace=True); b=search(**args,trace=True)
        self.assertEqual(a,b)
        self.assertTrue(a['trace'][7]['mode_after'])
        self.assertTrue(all(not t['scores'] for t in a['trace'][:8]))
        self.assertTrue(all(t['chosen']==t['native'] and not t['scores'] for t in a['trace'] if t['step']%4==0))
        self.assertGreater(a['counters']['probe_reads'],0)
        self.assertEqual(a['counters']['graph_distances'],len(args['vectors']))
        native=search(**args,scheduler=False)
        self.assertEqual(native['counters']['probe_reads'],0)
        self.assertEqual(a['ids'],native['ids'])

    def test_routes(self):
        self.assertEqual(route(10000,50,10)['route'],'exact')
        self.assertEqual(route(10000,1000,10)['route'],'pilot')
        self.assertEqual(route(10000,1000,10,7)['route'],'exact')
        self.assertEqual(route(10000,1000,10,8),{'route':'graph','ef':512})
        self.assertEqual(route(1000000,10000,10000,8)['reason'],'width_cap')

    def test_gate_second_boundary_and_zero_yield_native(self):
        # Complete 80-node graph: all later windows have zero remaining yield.
        # First 8 steps enable; following 64 steps form the next complete block.
        n=80
        r=search([[1,0] for _ in range(n)],
                 [[j for j in range(n) if j!=i] for i in range(n)],
                 set(range(n)),[0,0],0,k=10,ef=n,trace=True)
        self.assertEqual(len(r['trace']),80)
        self.assertTrue(r['trace'][7]['mode_after'])
        self.assertTrue(r['trace'][71]['mode_after'])
        self.assertTrue(all(t['native']==t['chosen'] for t in r['trace']))
        self.assertTrue(all(s['y']==0 for t in r['trace'] for s in t['scores']))
        self.assertEqual(r['ids'],list(range(10)))

    def test_full_search_heap_rejects_equal_distance(self):
        r=search([[1],[1],[1]],[[],[0],[1]],{0,1,2},[0],2,k=1,ef=1,trace=True)
        self.assertEqual(r['counters']['expansions'],1)
        self.assertEqual(r['ids'],[1])

    def test_empty_predicate(self):
        r=search([[0],[1]],[[1],[]],set(),[0],0,k=1,ef=2)
        self.assertEqual(r['ids'],[])
        self.assertEqual(r['counters']['fallback_distances'],0)

class ArchiveChecks(unittest.TestCase):
    def test_favor_scale_and_stop(self):
        self.assertGreater(adjusted_score(.64,False,.25),adjusted_score(1,True,.25))
        self.assertLess(.64+.25,1)  # Adding to squared distance reverses this choice.
        self.assertEqual(exclusion_distance(1,256,.2,.4),0)
        self.assertFalse(should_stop(2,1,256,128,256))
        self.assertTrue(should_stop(2,1,256,129,256))
        self.assertFalse(should_stop(2,1,128,100,256))

    def test_cost_profile_common_scaling(self):
        for r in rows('cost_profiles.csv'):
            rho,kappa=float(r['b_over_a']),float(r['c_over_a'])
            for degree,unseen,yield_count in [(32,6,2),(32,16,12),(8,2,1)]:
                normalized=yield_count/(degree+rho*unseen+kappa)
                raw=yield_count/(3.7*degree+3.7*rho*unseen+3.7*kappa)
                self.assertAlmostEqual(normalized,3.7*raw)

    def test_csv_shapes_and_units(self):
        for file in (ROOT/'data').glob('*.csv'):
            for row in rows(file.name):
                self.assertNotIn(None,row,f'{file.name}: extra CSV columns')
                self.assertNotIn(None,row.values(),f'{file.name}: missing CSV columns')
                for key,value in row.items():
                    if value and (key.endswith('_ms') or 'recall' in key):
                        if key!='mean_difference_ms': self.assertGreaterEqual(float(value),0)
                        if 'recall' in key: self.assertLessEqual(float(value),1)

    def test_articles_weighted_means(self):
        bins=rows('articles_bins.csv'); n=sum(int(b['requests']) for b in bins)
        self.assertEqual(n,10000)
        graph_n=sum(int(b['graph_requests']) for b in bins)
        self.assertEqual(graph_n,3200)
        main=next(r for r in rows('main.csv') if r['collection']=='Articles')
        for method in ['bpf','selfront']:
            total=graph_total=recall_total=0
            for b in bins:
                ng=int(b['graph_requests']); count=int(b['requests'])
                graph=float(b[method+'_graph_ms'] or 0)
                expected=(ng*graph+(count-ng)*float(b['exact_ms']))/count
                self.assertAlmostEqual(expected,float(b[method+'_all_ms']),places=9)
                total+=count*expected; graph_total+=ng*graph
                recall_total+=ng*float(b[method+'_graph_recall'] or 0)
            self.assertAlmostEqual(total/n,float(main[method+'_all_ms']),places=7)
            self.assertLessEqual(abs(graph_total/graph_n-float(main[method+'_graph_ms'])),.0005)
            self.assertLessEqual(abs(recall_total/graph_n-float(main[method+'_graph_recall'])),.000051)
            self.assertAlmostEqual(sum(float(r[method+'_ms']) for r in rows('cost.csv')),graph_total/graph_n,places=9)
            self.assertAlmostEqual(sum(float(r[method+'_ms']) for r in rows('quartiles.csv'))/4,graph_total/graph_n,places=9)

    def test_external_and_quality_context(self):
        for m,e in zip(rows('main.csv'),rows('external.csv')):
            self.assertEqual(m['collection'],e['collection'])
            self.assertEqual(float(m['selfront_all_ms']),float(e['selfront_ms']))
        for row in rows('adapter_recall.csv'):
            self.assertTrue(all(.95<=float(row[f'bin{i}'])<=1 for i in range(1,5)))
        for row in rows('quality_points.csv'):
            self.assertGreaterEqual(float(row['tuning_recall']),float(row['target']))
        ablations=rows('ablations.csv')
        self.assertTrue(all(float(r['recall'])>=.95 for r in ablations[:-1]))
        self.assertLess(float(ablations[-1]['recall']),.95)

if __name__=='__main__':
    unittest.main(verbosity=2)
