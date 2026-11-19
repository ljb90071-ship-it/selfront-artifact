"""Check that stopping probe reads preserves the full-budget search."""
import itertools
import json
from pathlib import Path
import random
import sys

from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from selfront import Config, choose_window, search


def exact_choice(candidates, cfg):
    """Use integer cross-products to compute the first maximum."""
    best_index, best_n, best_d = 0, 0, 1
    for i, draws in enumerate(candidates):
        useful = draws.count(2)
        unseen = useful + draws.count(1)
        numerator = 5 * useful
        denominator = cfg.s * (cfg.c + cfg.a * 5) + cfg.b * 5 * unseen
        if numerator * best_d > best_n * denominator:
            best_index, best_n, best_d = i, numerator, denominator
    return best_index


class Draws:
    """Return prescribed positions and count every consumed draw."""
    def __init__(self, positions):
        self.positions = iter(positions)
        self.drawn = 0

    def randrange(self, length):
        self.drawn += 1
        position = next(self.positions)
        assert 0 <= position < length
        return position


def finite_check():
    cfg = Config(s=4, a=1, b=10, c=2)
    # In each list position 0 is discovered, 1 is unseen but ineligible,
    # and 2 is unseen and eligible. Positions 3-4 complete degree five.
    adjacency = [list(range(5)), list(range(5, 10))]
    seen = {0, 5}
    eligible = {2, 7}
    window = [(1.0, 0), (1.0, 1)]
    cases = 0
    savings = Counter()
    grouped_savings = Counter()
    for draws in itertools.product(range(3), repeat=2 * cfg.s):
        rng = Draws(draws)
        winner, reads, _, _ = choose_window(
            window, adjacency, seen, eligible, rng, cfg, (2, 3))
        assert winner[1] == exact_choice((draws[:4], draws[4:]), cfg)
        assert rng.drawn == 8
        savings[8 - reads] += 1
        rng = Draws(draws)
        grouped, grouped_reads, _, _ = choose_window(
            window, adjacency, seen, eligible, rng, cfg, (2, 3),
            reuse_positions=True)
        assert winner == grouped and rng.drawn == 8
        grouped_savings[8 - grouped_reads] += 1
        cases += 1

    # Small rows form an exact scan. Check equality with the incumbent, for
    # which only the earlier native key or ID can win.
    cfg = Config(s=8, a=1, b=4, c=0)
    small_rows = ([1, 2, 3, 4], [1, 2, 3, 4])
    rng = random.Random(2)
    state = rng.getstate()
    winner, reads, checks, _ = choose_window(
        window, small_rows, set(), {1, 2, 3, 4}, rng, cfg, (2,))
    assert winner == window[0] and reads == 6 and checks == 1
    assert rng.getstate() == state
    return dict(two_candidate_sequences=cases,
                sequences_by_reads_skipped=dict(sorted(savings.items())),
                grouped_sequences_by_reads_skipped=dict(sorted(grouped_savings.items())),
                exact_scan_tie="same winner with two fewer metadata reads")


def circle_check():
    fixture = json.loads((ROOT / "examples/circle.json").read_text(encoding="utf-8"))
    fixture.pop("description")
    cfg = Config(**json.loads((ROOT / "configs/operator.json").read_text(encoding="utf-8")))
    exact = sorted(
        fixture["eligible"],
        key=lambda v: (sum((x - q)**2 for x, q in zip(
            fixture["vectors"][v], fixture["query"])), v),
    )[:fixture["k"]]
    configs = [((), False), ((4,), False), ((6,), False), ((4, 6), False),
               ((), True), ((6,), True)]
    results = []
    for checkpoints, reuse in configs:
        totals = Counter()
        for seed in range(24):
            fixture["seed"] = seed
            full = search(**fixture, cfg=cfg, trace=True)
            actual = search(**fixture, cfg=cfg, trace=True,
                            probe_checkpoints=checkpoints, reuse_probe_positions=reuse)
            for field in ("ids", "squared_distances", "fallback"):
                assert full[field] == actual[field]
            assert all(full["counters"][field] == actual["counters"][field]
                       for field in full["counters"] if field != "probe_reads")
            assert [step["chosen"] for step in full["trace"]] == [
                step["chosen"] for step in actual["trace"]]
            totals["full_metadata_reads"] += full["counters"]["probe_reads"]
            totals["metadata_reads"] += actual["counters"]["probe_reads"]
            totals["bound_checks"] += actual["counters"].get("probe_bound_checks", 0)
            totals["paired_expansions"] += len(actual["trace"])
            totals["truth_hits"] += len(set(exact) & set(actual["ids"]))
        results.append(dict(checkpoints=checkpoints, reuse_positions=reuse, seeds=24, **totals))
    return results


output = dict(finite_check=finite_check(), bottom_layer_pairs=circle_check())
(ROOT / "outputs/probe_bounds.json").write_text(
    json.dumps(output, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, indent=2))
