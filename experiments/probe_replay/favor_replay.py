"""Pair full and bounded observations inside the archived FAVOR-A scalar rules.

The CPU fixture builds one small, one-layer proximity graph with generated
vectors and predicates. It reports actual search work and retrieval results.
Distances for ground truth and for operator lookups share a precomputed vector
of query distances. This is a count experiment, with no wall-clock claim.
"""

import argparse
import csv
import hashlib
import heapq
import importlib.util
import json
import math
import random
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from probe_replay import ProbeWork, ScoreProfile, beats, choose, rate

HERE = Path(__file__).resolve().parent
CHECKPOINTS = ((4,), (6,), (4, 6))
WIDTH_PROFILES = [(384, 10), (512, 10), (768, 18), (1024, 18)]
SEEDS = (7393, 10301)
SELECTIVITIES = (0.007, 0.028, 0.115, 0.36)
K = 10


class PositionStream(random.Random):
    def __init__(self, seed):
        super().__init__(seed)
        self.digest = hashlib.sha256()

    def randrange(self, stop):
        position = super().randrange(stop)
        self.digest.update(struct.pack("<II", stop, position))
        return position


@dataclass
class Query:
    id: int
    bin: int
    distances: tuple
    eligible: frozenset
    truth: tuple
    entry: int


@dataclass
class Search:
    trace: list
    decisions: list
    results: tuple
    work: Counter
    probe: ProbeWork
    rng_hash: str
    rng_state: tuple


def normalize(rows):
    return rows / np.linalg.norm(rows, axis=1, keepdims=True)


def fixture():
    rng = np.random.default_rng(414115)
    groups, members, dims = 32, 64, 24
    labels = np.repeat(np.arange(groups), members)
    centers = normalize(rng.normal(size=(groups, dims)))
    points = normalize(centers[labels] + rng.normal(scale=0.24, size=(len(labels), dims)))
    sqdiff = 2 - 2 * (points @ points.T)
    np.fill_diagonal(sqdiff, np.inf)
    closest = np.argpartition(sqdiff, kth=63, axis=1)[:, :64]
    adjacency = []
    for v, unsorted in enumerate(closest):
        ordered = sorted(map(int, unsorted), key=lambda u: (sqdiff[v, u], u))
        neighbors = ordered[:28]
        membership = set(neighbors) | {v}
        while len(neighbors) < 32:
            u = int(rng.integers(len(points)))
            if u not in membership:
                membership.add(u)
                neighbors.append(u)
        adjacency.append(tuple(neighbors))
    anchor_ids = np.arange(0, len(points), 16)
    anchor_distances = np.sqrt(np.partition(sqdiff[anchor_ids], (15, 63), axis=1)[:, (15, 63)])
    d16, d64 = map(float, np.mean(anchor_distances, axis=0))
    queries = []
    portal_ids = np.arange(0, len(points), members)
    for selectivity_bin, target_sigma in enumerate(SELECTIVITIES, start=1):
        for replicate in range(6):
            theme = int(rng.integers(groups))
            q = normalize(centers[theme][None] + rng.normal(scale=0.20, size=(1, dims)))[0]
            distances = np.sqrt(np.maximum(0., 2 - 2 * (points @ q)))
            metadata = rng.normal(size=len(points))
            if replicate % 2 == 0:
                metadata += 2.25 * (labels == theme) + 1.5 * (centers[labels] @ centers[theme])
            count = round(target_sigma * len(points))
            eligible = frozenset(map(int, np.argpartition(metadata, -count)[-count:]))
            truth = tuple(sorted(eligible, key=lambda i: (distances[i], i))[:K])
            entry = int(portal_ids[np.argmin(distances[portal_ids])])
            queries.append(Query(len(queries), selectivity_bin, tuple(map(float, distances)), eligible, truth, entry))
    return adjacency, queries, d16, d64


def alignment(window, adjacency, discovered, eligible, profile):
    scores = []
    for _, vertex in window:
        neighbors = adjacency[vertex]
        unseen = [u for u in neighbors if u not in discovered]
        scores.append(rate(len(neighbors), len(neighbors), len(unseen), sum(u in eligible for u in unseen), profile))
    first = scores[0]
    if any(beats(challenger, first) for challenger in scores[1:]):
        return "alternative_better"
    return "native_best" if first[0] else "zero_yield"


def search(query, adjacency, width, profile, checkpoint, seed, anchors, adapter, reuse_choice=None):
    exclusion_distance, should_stop, archived_choice, archived_config = adapter
    rng = PositionStream(seed)
    work = Counter()
    probe = ProbeWork()
    eligible = query.eligible
    sigma = len(eligible) / len(adjacency)
    if sigma < 0.01:
        work["exact_route_distances"] = len(eligible)
        return Search([], [], query.truth, work, probe, rng.digest.hexdigest(), rng.getstate())

    penalty = exclusion_distance(sigma, width, *anchors)
    keys = tuple(d + (0 if v in eligible else penalty) for v, d in enumerate(query.distances))
    entry = query.entry
    visited = {entry}
    pending = [(keys[entry], entry)]
    retained = [(-keys[entry], -entry)]
    selected_in_heap = int(entry in eligible)
    work.update({"graph_distances": 1, "candidate_pushes": 1, "retained_pushes": 1})
    observed_eligible = observed_repeat = 0
    next_block = 8
    enabled = False
    trace = []
    decisions = []
    while pending:
        first_key, _ = pending[0]
        worst_key = -retained[0][0]
        if should_stop(first_key, worst_key, len(retained), selected_in_heap, width):
            break
        native = heapq.heappop(pending)
        work["candidate_pops"] += 1
        chosen = native
        if enabled and (len(trace) + 1) % 4 != 0:
            bound = worst_key if len(retained) == width and selected_in_heap * 2 > width else math.inf
            bound = min(bound, 1.1 * native[0] + 1e-6)
            window = [native]
            while len(window) < 4 and pending and pending[0][0] <= bound:
                window.append(heapq.heappop(pending))
                work["candidate_pops"] += 1
            if len(window) > 1:
                draws = sum(profile.samples for _, v in window if len(adjacency[v]) > profile.samples)
                if checkpoint is not None and reuse_choice is not None:
                    (_, winner), reads, checks, details = reuse_choice(
                        window, adjacency, visited, eligible, rng, archived_config,
                        checkpoint, trace=True, reuse_positions=True,
                    )
                    cuts = sum("pruned_after" in candidate for candidate in details)
                    current = ProbeWork(positions=reads, draws=draws, bounds=checks, cuts=cuts)
                    group = None
                elif checkpoint is not None:
                    winner, current = choose(
                        tuple(v for _, v in window), adjacency, visited, eligible, rng, profile, checkpoint,
                    )
                    group = None
                else:
                    winner, reads = archived_choice(
                        window, adjacency, visited, eligible, rng, archived_config,
                    )
                    current = ProbeWork(positions=reads, draws=draws)
                    group = alignment(window, adjacency, visited, eligible, profile)
                probe.add(current)
                decisions.append((len(trace), tuple(v for _, v in window), winner, current, group))
                chosen = (keys[winner], winner)
                for pair in window:
                    if pair[1] != winner:
                        heapq.heappush(pending, pair)
                        work["candidate_pushes"] += 1
        vertex = chosen[1]
        discovered_now = []
        for u in adjacency[vertex]:
            work["scan_positions"] += 1
            accepted = u in eligible
            observed_eligible += accepted
            if u in visited:
                observed_repeat += accepted
                continue
            visited.add(u)
            discovered_now.append(u)
            work["graph_distances"] += 1
            key = keys[u]
            if len(retained) < width or key < -retained[0][0]:
                heapq.heappush(pending, (key, u))
                heapq.heappush(retained, (-key, -u))
                selected_in_heap += accepted
                work["candidate_pushes"] += 1
                work["retained_pushes"] += 1
                if len(retained) > width:
                    _, removed = heapq.heappop(retained)
                    selected_in_heap -= (-removed in eligible)
                    work["retained_pops"] += 1
        trace.append((vertex, tuple(discovered_now)))
        if len(trace) == next_block:
            enabled = observed_eligible >= 32 and observed_repeat / observed_eligible >= .35
            next_block += 64
            observed_eligible = observed_repeat = 0

    available = [v for _, neg in retained if (v := -neg) in eligible]
    results = tuple(sorted(available, key=lambda i: (query.distances[i], i))[:K])
    if len(results) < min(K, len(eligible)):
        results = query.truth
        work["fallback_distances"] = len(eligible)
    work["expansions"] = len(trace)
    return Search(trace, decisions, results, work, probe, rng.digest.hexdigest(), rng.getstate())


def compare(full, bounded):
    assert full.trace == bounded.trace
    assert full.work == bounded.work
    assert full.results == bounded.results
    assert full.rng_hash == bounded.rng_hash and full.rng_state == bounded.rng_state
    assert len(full.decisions) == len(bounded.decisions)
    assert full.probe.draws == bounded.probe.draws
    assert full.probe.positions >= bounded.probe.positions
    for f, b in zip(full.decisions, bounded.decisions):
        assert f[:3] == b[:3]
        assert f[3].positions >= b[3].positions and f[3].draws == b[3].draws


def summarize(rows):
    fields = (
        "scheduled_windows", "expansions", "fallback_distances", "exact_route_distances",
        "full_positions", "bounded_positions", "draws", "bound_checks", "cut_lists",
    )
    result = {key: sum(r[key] for r in rows) for key in fields}
    if "impossible_at_entry" in rows[0]:
        result["impossible_at_entry"] = sum(r["impossible_at_entry"] for r in rows)
    result["requests"] = len(rows)
    result["identical_recall"] = sum(r["recall"] for r in rows) / len(rows)
    result["saved_positions"] = result["full_positions"] - result["bounded_positions"]
    if not rows[0]["checkpoint"].startswith("reuse"):
        result["saved_positions_per_check"] = (
            result["saved_positions"] / result["bound_checks"] if result["bound_checks"] else None
        )
    result["fraction_probes_removed"] = (
        result["saved_positions"] / result["full_positions"] if result["full_positions"] else None
    )
    result["no_saving_scheduled_requests"] = sum(
        r["scheduled_windows"] > 0 and r["full_positions"] == r["bounded_positions"] for r in rows
    )
    return result


def dump_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def import_reuse(core_path):
    source = core_path.read_bytes()
    spec = importlib.util.spec_from_file_location("r014_reuse", core_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(source, str(core_path), "exec"), module.__dict__)
    return module.choose_window, hashlib.sha256(source).hexdigest()


def run(archive, reuse_core):
    sys.path.insert(0, str(archive))
    from favor_rules import exclusion_distance, should_stop
    from host_window import choose_expansion
    from selfront import Config

    reuse_choice, reuse_hash = import_reuse(reuse_core) if reuse_core else (None, None)
    if reuse_core:
        modes = {"reuse": (), "reuse+6": (6,)}
        name = "favor_reuse_replay"
    else:
        modes = {"+".join(map(str, cfg)): cfg for cfg in CHECKPOINTS}
        name = "favor_replay"
    adjacency, queries, d16, d64 = fixture()
    rows = []
    groups = {}
    for width, rho in WIDTH_PROFILES:
        profile = ScoreProfile(b=rho)
        adapter = (exclusion_distance, should_stop, choose_expansion, Config(a=1, b=rho, c=2))
        for query in queries:
            for seed in SEEDS:
                pair_seed = seed + query.id * 10007
                full = search(query, adjacency, width, profile, None, pair_seed, (d16, d64), adapter)
                reuse_only = None
                for label, cfg in modes.items():
                    bounded = search(
                        query, adjacency, width, profile, cfg, pair_seed, (d16, d64), adapter, reuse_choice,
                    )
                    compare(full, bounded)
                    if label == "reuse":
                        reuse_only = bounded
                    if label == "reuse+6":
                        compare(reuse_only, bounded)
                    for f, b in zip(full.decisions, bounded.decisions):
                        group = groups.setdefault((width, label, f[4]), Counter())
                        group.update({
                            "windows": 1,
                            "full_positions": f[3].positions,
                            "saved_positions": f[3].positions - b[3].positions,
                            "bound_checks": b[3].bounds,
                        })
                        if not reuse_core:
                            group["impossible_at_entry"] += b[3].impossible_at_entry
                    row = {
                        "width": width, "rho": rho, "checkpoint": label,
                        "query": query.id, "bin": query.bin, "seed": pair_seed,
                        "recall": len(set(full.results) & set(query.truth)) / len(query.truth),
                        "scheduled_windows": len(full.decisions),
                        "expansions": full.work["expansions"],
                        "fallback_distances": full.work["fallback_distances"],
                        "exact_route_distances": full.work["exact_route_distances"],
                        "full_positions": full.probe.positions, "bounded_positions": bounded.probe.positions,
                        "draws": full.probe.draws, "bound_checks": bounded.probe.bounds,
                        "cut_lists": bounded.probe.cuts,
                    }
                    if not reuse_core:
                        row["impossible_at_entry"] = bounded.probe.impossible_at_entry
                    rows.append(row)
    dump_csv(HERE / f"{name}_requests.csv", rows)
    grouped = [dict(width=w, checkpoint=c, state=g, **n) for (w, c, g), n in sorted(groups.items())]
    dump_csv(HERE / f"{name}_windows.csv", grouped)
    selected = []
    for width, rho in WIDTH_PROFILES:
        for label in modes:
            subset = [r for r in rows if r["width"] == width and r["checkpoint"] == label]
            selected.append(dict(width=width, rho=rho, checkpoint=label, **summarize(subset)))
    report = {
        "vertices": len(adjacency), "degree": len(adjacency[0]), "queries": len(queries),
        "seeds": len(SEEDS), "paired_requests": len(rows), "position_streams_and_trace_match": True,
        "settings": selected,
    }
    if reuse_core:
        report["reuse_core_sha256"] = reuse_hash
        report["marginal_cutoff"] = []
        for width, _ in WIDTH_PROFILES:
            reuse, both = [s for s in selected if s["width"] == width]
            extra_saved = reuse["bounded_positions"] - both["bounded_positions"]
            report["marginal_cutoff"].append({
                "width": width, "full_positions": reuse["full_positions"],
                "reuse_positions": reuse["bounded_positions"], "reuse_bound_positions": both["bounded_positions"],
                "saved_by_reuse": reuse["saved_positions"], "extra_saved_by_bound": extra_saved,
                "extra_saved_fraction_after_reuse": extra_saved / reuse["bounded_positions"],
                "bound_checks": both["bound_checks"],
                "extra_positions_per_bound_check": extra_saved / both["bound_checks"],
            })
        cells = report["marginal_cutoff"]
        totals = {
            name: sum(cell[name] for cell in cells)
            for name in ("full_positions", "reuse_positions", "reuse_bound_positions",
                         "saved_by_reuse", "extra_saved_by_bound", "bound_checks")
        }
        totals["reuse_saved_fraction"] = totals["saved_by_reuse"] / totals["full_positions"]
        totals["extra_saved_fraction_after_reuse"] = totals["extra_saved_by_bound"] / totals["reuse_positions"]
        totals["extra_positions_per_bound_check"] = totals["extra_saved_by_bound"] / totals["bound_checks"]
        report["marginal_cutoff_pooled"] = totals
        states = []
        for state in sorted({g["state"] for g in grouped}):
            reuse = [g for g in grouped if g["checkpoint"] == "reuse" and g["state"] == state]
            both = [g for g in grouped if g["checkpoint"] == "reuse+6" and g["state"] == state]
            positions_after_reuse = sum(g["full_positions"] - g["saved_positions"] for g in reuse)
            extra = sum(g["saved_positions"] for g in both) - sum(g["saved_positions"] for g in reuse)
            states.append({
                "state": state,
                "windows": sum(g["windows"] for g in reuse),
                "positions_after_reuse": positions_after_reuse,
                "extra_saved_by_bound": extra,
                "bound_checks": sum(g["bound_checks"] for g in both),
                "extra_saved_fraction_after_reuse": extra / positions_after_reuse,
            })
        report["marginal_cutoff_by_state"] = states
    (HERE / f"{name}_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-src", type=Path,
        default=HERE.parents[1] / "src",
        help="directory containing the FAVOR-A scalar rules and full-window scorer",
    )
    parser.add_argument("--reuse-core", type=Path, help="shared selfront.py exposing choose_window and row reuse")
    args = parser.parse_args()
    run(args.archive_src, args.reuse_core)
