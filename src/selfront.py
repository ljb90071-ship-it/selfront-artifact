"""Readable bottom-layer SelFront reference operator; Python standard library only."""
from dataclasses import dataclass
import heapq
import math
import random


@dataclass(frozen=True)
class Config:
    w: int = 4
    s: int = 8
    h: int = 4
    epsilon: float = 0.1
    tau: float = 1e-6
    a: float = 1.0
    b: float = 4.0
    c: float = 0.0
    initial_block: int = 8
    block: int = 64
    min_eligible: int = 32
    overlap: float = 0.35

    def __post_init__(self):
        if min(self.w, self.s, self.h, self.initial_block, self.block) < 1:
            raise ValueError('counts and periods must be positive')
        if self.a <= 0 or min(self.b, self.c, self.epsilon, self.tau) < 0:
            raise ValueError('invalid cost or distance parameters')
        if self.min_eligible < 1 or not 0 <= self.overlap <= 1:
            raise ValueError('invalid gate parameters')


def squared_distance(x, q):
    if len(x) != len(q) or not all(math.isfinite(v) for v in (*x, *q)):
        raise ValueError('vectors must have matching dimensions and finite values')
    return sum((a-b)**2 for a, b in zip(x, q))


def probe(neighbors, discovered, eligible, rng, cfg):
    """Return (Uhat,Yhat,score,metadata_reads), without modifying query state."""
    d = len(neighbors)
    if not d:
        return 0.0, 0.0, 0.0, 0
    positions = range(d) if d <= cfg.s else (rng.randrange(d) for _ in range(cfg.s))
    unseen = useful = reads = 0
    for i in positions:
        v = neighbors[i]
        fresh, accepted = v not in discovered, v in eligible
        unseen += fresh
        useful += fresh and accepted
        reads += 1
    scale = d / reads
    u, y = unseen*scale, useful*scale
    return u, y, y/(cfg.c + cfg.a*d + cfg.b*u), reads


def route(n, eligible_count, k, pilot_eligible=None, beta=4.0):
    """Shared route from supplied native-pilot count. Does not run an HNSW pilot."""
    if n < 1 or not 0 <= eligible_count <= n or k < 1 or beta <= 0:
        raise ValueError('invalid routing input')
    sigma = eligible_count/n
    if eligible_count < k or sigma < .01:
        return {'route': 'exact', 'reason': 'cardinality_or_selectivity'}
    if pilot_eligible is None:
        return {'route': 'pilot', 'width': 128}
    if not 0 <= pilot_eligible <= 128:
        raise ValueError('pilot count must be in [0,128]')
    if pilot_eligible < 8:
        return {'route': 'exact', 'reason': 'pilot'}
    ef = 2**math.ceil(math.log2(max(256, beta*k/sigma)))
    return {'route': 'graph', 'ef': ef} if ef <= 16384 else {'route': 'exact', 'reason': 'width_cap'}


def search(vectors, adjacency, eligible, query, entry, k=10, ef=256,
           seed=0, scheduler=True, cfg=Config(), trace=False):
    """Run one fresh graph invocation, then exact cardinality fallback if needed.

    IDs are contiguous integers. C is a min heap; W and R are bounded max heaps.
    Optional trace is diagnostic storage, not part of the O(w) scheduler state.
    The caller supplies a fixed bottom-layer graph, bitmap and entry.
    """
    n = len(vectors)
    if not 0 <= entry < n or len(adjacency) != n or k < 1 or ef < 1:
        raise ValueError('invalid graph/search dimensions')
    eligible = frozenset(eligible)
    if not eligible <= set(range(n)):
        raise ValueError('eligible ID outside graph')
    if any(len(set(ns)) != len(ns) or any(not 0 <= v < n for v in ns) for ns in adjacency):
        raise ValueError('adjacency must contain distinct valid IDs')
    if any(len(v) != len(query) or not all(math.isfinite(x) for x in v) for v in vectors):
        raise ValueError('invalid vectors')
    rng = random.Random(seed)
    discovered = {entry}
    d0 = squared_distance(vectors[entry], query)
    candidates, best = [(d0, entry)], [(-d0, -entry)]
    results = [(-d0, -entry)] if entry in eligible else []
    counters = dict(expansions=0, graph_distances=1, adjacency_reads=0,
                    probe_reads=0, fallback_distances=0, scheduled_steps=0)
    history = []
    enabled = False
    observed = duplicate = block_steps = 0
    block_length = cfg.initial_block

    def bounded_add(heap, dist, vertex, capacity, distance_only=False):
        item = (-dist, -vertex)
        if len(heap) < capacity:
            heapq.heappush(heap, item)
            return True
        improves = dist < -heap[0][0] if distance_only else item > heap[0]
        if improves:
            heapq.heapreplace(heap, item)
            return True
        return False

    while candidates:
        native = candidates[0]
        bound = -best[0][0] if len(best) == ef else math.inf
        if native[0] > bound:
            break
        periodic = (counters['expansions']+1) % cfg.h == 0
        can_schedule = scheduler and enabled and not periodic
        chosen = heapq.heappop(candidates)
        scores = []
        if can_schedule:
            window = [chosen]
            cap = min(bound, (1+cfg.epsilon)*native[0]+cfg.tau)
            while candidates and len(window) < cfg.w and candidates[0][0] <= cap:
                window.append(heapq.heappop(candidates))
            if len(window) > 1:
                for dist, vertex in window:
                    u, y, score, reads = probe(adjacency[vertex], discovered, eligible, rng, cfg)
                    counters['probe_reads'] += reads
                    scores.append(dict(id=vertex, distance=dist, u=u, y=y, score=score))
                winner = min(scores, key=lambda r: (-r['score'], r['distance'], r['id']))
                chosen = (winner['distance'], winner['id'])
                counters['scheduled_steps'] += 1
            for candidate in window:
                if candidate != chosen:
                    heapq.heappush(candidates, candidate)
        before_mode = enabled
        for neighbor in adjacency[chosen[1]]:
            counters['adjacency_reads'] += 1
            fresh = neighbor not in discovered
            if scheduler:
                accepted = neighbor in eligible
                observed += accepted
                duplicate += accepted and not fresh
            if not fresh:
                continue
            discovered.add(neighbor)
            dist = squared_distance(vectors[neighbor], query)
            counters['graph_distances'] += 1
            if bounded_add(best, dist, neighbor, ef, distance_only=True):
                heapq.heappush(candidates, (dist, neighbor))
            if neighbor in eligible:
                bounded_add(results, dist, neighbor, k)
        counters['expansions'] += 1
        if scheduler:
            block_steps += 1
            if block_steps == block_length:
                enabled = observed >= cfg.min_eligible and duplicate/observed >= cfg.overlap
                observed = duplicate = block_steps = 0
                block_length = cfg.block
        if trace:
            history.append(dict(step=counters['expansions'], native=native[1],
                                chosen=chosen[1], mode_before=before_mode, mode_after=enabled,
                                periodic=periodic, scores=scores, discovered=len(discovered)))
    answer = sorted((-d, -v) for d, v in results)
    fallback = len(answer) < k
    if fallback:
        answer = sorted((squared_distance(vectors[v], query), v) for v in eligible)[:k]
        counters['fallback_distances'] = len(eligible)
    return dict(ids=[v for _, v in answer], squared_distances=[d for d, _ in answer],
                fallback=fallback, counters=counters, trace=history)
