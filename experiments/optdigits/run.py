"""Paired probe-count experiment with the original OptDigits writer split."""
import argparse
import csv
import gzip
import hashlib
import heapq
import importlib.util
import io
import json
import math
import platform
import random
import sys
from pathlib import Path
from zipfile import ZipFile

import numpy as np


HERE = Path(__file__).resolve().parent
DATA_SHA256 = "0d7b054fea010270e9b3f06411c654c5e59547732ad626381980baffe0a23fb0"
DEGREE, EF, TOP_K, WIDTH, BUDGET = 32, 64, 10, 4, 8
A, B, C = 1, 4, 2
SEEDS = (0, 1, 2)
PREDICATES = ("same_digit", "same_parity", "opposite_parity")
CHECKPOINTS = (4, 6)


def load(archive):
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != DATA_SHA256:
        raise ValueError(f"Unexpected UCI archive SHA-256: {digest}")
    with ZipFile(archive) as source:
        train, test = (
            np.loadtxt(io.BytesIO(source.read("optdigits." + ext)), delimiter=",", dtype=np.int32)
            for ext in ("tra", "tes")
        )
    assert train.shape == (3823, 65) and test.shape == (1797, 65)
    train_rows = {r.tobytes() for r in train[:, :64]}
    test_rows = {r.tobytes() for r in test[:, :64]}
    assert len(train_rows) == len(train) and len(test_rows) == len(test)
    assert train_rows.isdisjoint(test_rows)
    return train[:, :64].copy(), train[:, 64], test[:, :64].copy(), test[:, 64]


def build_graph(vectors):
    # The UCI integer feature range makes these float64 operations exact.
    x = vectors.astype(np.float64)
    sq = np.einsum("ij,ij->i", x, x)
    distances = sq[:, None] + sq[None, :] - 2 * (x @ x.T)
    entry = int(distances.sum(axis=1).argmin())
    np.fill_diagonal(distances, np.inf)
    adjacency = np.argsort(distances, axis=1, kind="stable")[:, :DEGREE].tolist()
    reachable = {entry}
    frontier = [entry]
    while frontier:
        for neighbor in adjacency[frontier.pop()]:
            if neighbor not in reachable:
                reachable.add(neighbor)
                frontier.append(neighbor)
    return adjacency, entry, len(reachable)


def choose(window, adjacency, discovered, eligible, rng, lazy):
    """Evaluate native-first completely. At checkpoints, skip only losing tails."""
    best = window[0]
    best_num, best_den = 0, 1
    reads = draws = checks = equal_cutoffs = pruned4 = pruned6 = 0
    for rank, candidate in enumerate(window):
        neighbors = adjacency[candidate[1]]
        degree = len(neighbors)
        if degree == 0:
            continue
        budget = min(BUDGET, degree)
        if degree > BUDGET:
            # Draw the full plan in both variants, without reading neighbor IDs.
            positions = [rng.randrange(degree) for _ in range(budget)]
            draws += budget
        else:
            positions = range(degree)
        base = budget * (C + A * degree)
        unseen = useful = 0
        for prefix, position in enumerate(positions, 1):
            neighbor = neighbors[position]
            fresh = not discovered[neighbor]
            accepted = eligible[neighbor >> 3] & (1 << (neighbor & 7))
            unseen += fresh
            useful += fresh and bool(accepted)
            reads += 1
            if lazy and rank and prefix in CHECKPOINTS and prefix < budget:
                checks += 1
                remaining = budget - prefix
                upper_num = degree * (useful + remaining)
                upper_den = base + B * degree * (unseen + remaining)
                difference = upper_num * best_den - best_num * upper_den
                # Earlier incumbents win exact ties in (native key, ID) order.
                if difference <= 0:
                    equal_cutoffs += difference == 0
                    pruned4 += prefix == 4
                    pruned6 += prefix == 6
                    break
        else:
            numerator = degree * useful
            denominator = base + B * degree * unseen
            if numerator * best_den > best_num * denominator:
                best, best_num, best_den = candidate, numerator, denominator
    return best, reads, draws, checks, equal_cutoffs, pruned4, pruned6


def search(vectors, adjacency, entry, query, eligible, eligible_ids, role, seed):
    def distance(vertex):
        delta = vectors[vertex] - query
        return int(delta @ delta)

    def accepts(vertex):
        return bool(eligible[vertex >> 3] & (1 << (vertex & 7)))

    rng = random.Random(seed)
    discovered = bytearray(len(vectors))
    discovered[entry] = 1
    first_distance = distance(entry)
    candidates, best = [(first_distance, entry)], [(-first_distance, -entry)]
    results = [(-first_distance, -entry)] if accepts(entry) else []
    distances = 1
    path, windows, saved_by_step = [], [], []
    reads = draws = checks = ties = pruned4 = pruned6 = 0
    observed = duplicate = block_steps = 0
    block_length, enabled = 8, False
    reorderings = 0

    while candidates:
        bound = -best[0][0] if len(best) == EF else math.inf
        if candidates[0][0] > bound:
            break
        native = chosen = heapq.heappop(candidates)
        if enabled and (len(path) + 1) % 4:
            window = [native]
            while candidates and len(window) < WIDTH:
                next_distance = candidates[0][0]
                if next_distance > bound or 10 * next_distance > 11 * native[0]:
                    break
                window.append(heapq.heappop(candidates))
            if len(window) > 1:
                chosen, taken, planned, tested, equal, p4, p6 = choose(
                    window, adjacency, discovered, eligible, rng, role == "lazy"
                )
                windows.append(tuple(window))
                reads += taken
                draws += planned
                checks += tested
                ties += equal
                pruned4 += p4
                pruned6 += p6
                saved_by_step.append(sum(min(BUDGET, len(adjacency[v])) for _, v in window) - taken)
            for candidate in window:
                if candidate != chosen:
                    heapq.heappush(candidates, candidate)
        reorderings += chosen != native
        path.append(chosen[1])
        for neighbor in adjacency[chosen[1]]:
            fresh = not discovered[neighbor]
            accepted = accepts(neighbor) if fresh or role != "native" else False
            if role != "native":
                observed += accepted
                duplicate += accepted and not fresh
            if not fresh:
                continue
            discovered[neighbor] = 1
            d = distance(neighbor)
            distances += 1
            item = (-d, -neighbor)
            if len(best) < EF:
                heapq.heappush(best, item)
                heapq.heappush(candidates, (d, neighbor))
            elif d < -best[0][0]:
                heapq.heapreplace(best, item)
                heapq.heappush(candidates, (d, neighbor))
            if accepted and len(results) < TOP_K:
                heapq.heappush(results, item)
            elif accepted and item > results[0]:
                heapq.heapreplace(results, item)
        if role != "native":
            block_steps += 1
            if block_steps == block_length:
                enabled = observed >= 32 and 100 * duplicate >= 35 * observed
                observed = duplicate = block_steps = 0
                block_length = 64

    fallback = len(results) < TOP_K
    if fallback:
        answer = heapq.nsmallest(TOP_K, ((distance(v), v) for v in eligible_ids))
    else:
        answer = sorted((-d, -v) for d, v in results)
    stats = dict(expansions=len(path), adjacency_reads=sum(len(adjacency[v]) for v in path),
                 graph_distances=distances, fallback_distances=len(eligible_ids) if fallback else 0,
                 scheduled=len(windows), reordered=reorderings, probe_reads=reads, random_draws=draws,
                 bound_checks=checks, equal_cutoffs=ties, pruned4=pruned4, pruned6=pruned6,
                 unsaved_windows=len(windows) - sum(saved > 0 for saved in saved_by_step))
    return (tuple(v for _, v in answer), path, windows, rng.getstate(), stats)


def masks(labels):
    index = {}
    parity = labels % 2
    for digit in range(10):
        selections = (labels == digit, parity == digit % 2, parity != digit % 2)
        for name, selected in zip(PREDICATES, selections):
            index[name, digit] = (np.packbits(selected, bitorder="little").tobytes(),
                                  np.flatnonzero(selected).tolist())
    return index


def reference_check(module, own, vectors, adjacency, entry, query, ids, role, seed):
    stats = own[4]
    reference = module.search(
        vectors, adjacency, ids, query, entry, k=TOP_K, ef=EF, seed=seed, scheduler=role != "native",
        cfg=module.Config(a=A, b=B, c=C, tau=0), trace=True,
        probe_checkpoints=CHECKPOINTS if role == "lazy" else (),
    )
    assert list(own[0]) == reference["ids"]
    assert own[1] == [row["chosen"] for row in reference["trace"]]
    for name in ("expansions", "graph_distances", "adjacency_reads", "probe_reads", "fallback_distances"):
        assert stats[name] == reference["counters"][name]
    assert stats["scheduled"] == reference["counters"]["scheduled_steps"]
    assert stats["bound_checks"] == reference["counters"].get("probe_bound_checks", 0)


def experiment(vectors, labels, queries, query_labels, adjacency, entry, reference):
    records = []
    mask_index = masks(labels)
    ref_vectors = vectors.tolist() if reference else None
    crosschecks = 0
    for qid, (query, digit) in enumerate(zip(queries, query_labels)):
        delta = vectors - query
        truth_distance = np.einsum("ij,ij->i", delta, delta)
        for predicate in PREDICATES:
            mask, ids = mask_index[predicate, digit]
            truth = set(heapq.nsmallest(TOP_K, ids, key=lambda v: (truth_distance[v], v)))
            assert len(truth) == TOP_K
            native = search(vectors, adjacency, entry, query, mask, ids, "native", 0)
            if reference and qid < 3:
                reference_check(reference, native, ref_vectors, adjacency, entry, query.tolist(), ids, "native", 0)
                crosschecks += 1
            seed_paths, seed_answers, first_row = set(), set(), len(records)
            for replicate in SEEDS:
                seed = (replicate << 32) | qid
                full = search(vectors, adjacency, entry, query, mask, ids, "full", seed)
                lazy = search(vectors, adjacency, entry, query, mask, ids, "lazy", seed)
                assert full[:4] == lazy[:4], (qid, predicate, replicate)
                fs, ls = full[4], lazy[4]
                for name in ("adjacency_reads", "graph_distances", "fallback_distances",
                             "scheduled", "reordered", "random_draws"):
                    assert fs[name] == ls[name]
                assert fs["probe_reads"] - ls["probe_reads"] == 4 * ls["pruned4"] + 2 * ls["pruned6"]
                if reference and qid < 3 and replicate == SEEDS[0]:
                    for role, run in (("full", full), ("lazy", lazy)):
                        reference_check(reference, run, ref_vectors, adjacency, entry, query.tolist(), ids, role, seed)
                        crosschecks += 1
                seed_paths.add(tuple(full[1]))
                seed_answers.add(full[0])
                row = dict(query=qid, digit=int(digit), predicate=predicate, eligible=len(ids), seed=replicate,
                           native_hits=len(truth.intersection(native[0])), paired_hits=len(truth.intersection(full[0])),
                           same_native_path=native[1] == full[1], same_native_answer=native[0] == full[0],
                           full_probe_reads=fs["probe_reads"])
                row.update(("native_" + key, value) for key, value in native[4].items()
                           if key in ("expansions", "adjacency_reads", "graph_distances", "fallback_distances"))
                row.update(("lazy_" + key, value) for key, value in ls.items())
                records.append(row)
            for row in records[first_row:]:
                row.update(seed_paths=len(seed_paths), seed_answers=len(seed_answers))
    return records, crosschecks


def summarize(records):
    summary = {}
    for predicate in (*PREDICATES, "pooled"):
        rows = [r for r in records if predicate == "pooled" or r["predicate"] == predicate]
        active = [r for r in rows if r["full_probe_reads"]]
        approximate = [r for r in rows if not (r["native_fallback_distances"] or r["lazy_fallback_distances"])]
        sums = {key: sum(row[key] for row in rows) for key in rows[0]
                if key.startswith(("native_", "lazy_", "full_", "same_native_")) or key == "paired_hits"}
        summary[predicate] = dict(
            query_predicate_pairs=len(rows) // len(SEEDS), query_seed_rows=len(rows),
            eligible_range=[min(r["eligible"] for r in rows), max(r["eligible"] for r in rows)],
            native_fallbacks=sum(bool(r["native_fallback_distances"]) for r in rows),
            paired_fallbacks=sum(bool(r["lazy_fallback_distances"]) for r in rows),
            rows_with_sampling=len(active),
            active_rows_without_savings=sum(r["full_probe_reads"] == r["lazy_probe_reads"] for r in active),
            seed_sensitive_paths=sum(r["seed_paths"] > 1 for r in rows if r["seed"] == SEEDS[0]),
            seed_sensitive_answers=sum(r["seed_answers"] > 1 for r in rows if r["seed"] == SEEDS[0]),
            paired_recall_below_native=sum(r["paired_hits"] < r["native_hits"] for r in rows),
            paired_recall_above_native=sum(r["paired_hits"] > r["native_hits"] for r in rows),
            joint_approximate_rows=len(approximate),
            native_approximate_hits=sum(r["native_hits"] for r in approximate),
            paired_approximate_hits=sum(r["paired_hits"] for r in approximate),
            **sums,
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=HERE / "optdigits-uci.zip")
    parser.add_argument("--reference", type=Path, help="Optional read-only selfront.py cross-check")
    parser.add_argument("--limit", type=int, default=1797, choices=range(1, 1798), metavar="1..1797")
    parser.add_argument("--write", action="store_true", help="Write the run's JSON and per-request CSV.gz")
    args = parser.parse_args()
    reference = None
    reference_hash = None
    if args.reference:
        sys.dont_write_bytecode = True
        reference_hash = hashlib.sha256(args.reference.read_bytes()).hexdigest()
        spec = importlib.util.spec_from_file_location("selfront_reference", args.reference)
        reference = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = reference
        spec.loader.exec_module(reference)
    vectors, labels, queries, classes = load(args.archive)
    adjacency, entry, reachable = build_graph(vectors)
    rows, crosschecks = experiment(
        vectors, labels, queries[:args.limit], classes[:args.limit], adjacency, entry, reference
    )
    output = {
        "data_sha256": DATA_SHA256,
        "software": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
        "graph": {"indexed_rows": len(vectors), "dimension": vectors.shape[1], "degree": DEGREE,
                  "entry_id": entry, "reachable_from_entry": reachable, "ef": EF},
        "setup": {"k": TOP_K, "window": WIDTH, "probe_budget": BUDGET, "checkpoints": CHECKPOINTS,
                  "seeds": SEEDS, "cost": [A, B, C], "distance_cap_ratio": 1.1},
        "per_query_seed_full_lazy_matches": len(rows),
        "optional_reference_crosschecks": crosschecks,
        "optional_reference_sha256": reference_hash,
        "summary": summarize(rows),
    }
    if args.write:
        (HERE / "results.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        with gzip.open(HERE / "per_request.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
