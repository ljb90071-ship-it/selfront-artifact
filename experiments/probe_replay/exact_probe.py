"""Exact position and comparison counts for fully specified query windows."""

import csv
import json
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

from probe_replay import ScoreProfile, beats, budgets, choose, count_states, rate, verify_upper_bound


@lru_cache(maxsize=None)
def score_paths(degree, unseen, useful, incumbent, checkpoints, profile):
    """Return exact winner-score distribution and expected work for one list."""
    states = Counter({(0, 0): 1})
    winners = Counter()
    reads = bounds = cuts = Fraction(0)
    budget = profile.samples
    outcomes = [
        (0, 0, degree - unseen),
        (1, 0, unseen - useful),
        (1, 1, useful),
    ]
    for prefix in range(1, budget + 1):
        reads += Fraction(sum(states.values()), degree ** (prefix - 1))
        following = Counter()
        for (u, y), weight in states.items():
            for delta_u, delta_y, multiplicity in outcomes:
                if multiplicity:
                    following[u + delta_u, y + delta_y] += weight * multiplicity
        states = following
        if prefix in checkpoints:
            bounds += Fraction(sum(states.values()), degree ** prefix)
            remaining = budget - prefix
            for u, y in count_states(prefix):
                upper = rate(degree, budget, u + remaining, y + remaining, profile)
                if not beats(upper, incumbent):
                    probability = Fraction(states.pop((u, y), 0), degree ** prefix)
                    winners[incumbent] += probability
                    cuts += probability

    for (u, y), weight in states.items():
        numerator, denominator = rate(degree, budget, u, y, profile)
        winner = (numerator, denominator) if beats((numerator, denominator), incumbent) else incumbent
        canonical = Fraction(*winner)
        winners[canonical.numerator, canonical.denominator] += Fraction(weight, degree ** budget)
    assert sum(winners.values()) == 1
    return winners, reads, bounds, cuts


def evaluate_window(window, checkpoints, profile):
    incumbents = Counter({(0, 1): Fraction(1)})
    total_reads = total_bounds = total_cuts = Fraction(0)
    for rank, (unseen, useful) in enumerate(window):
        following = Counter()
        for incumbent, probability in incumbents.items():
            winners, reads, bounds, cuts = score_paths(
                32, unseen, useful, incumbent, checkpoints if rank else (), profile,
            )
            for winner, weight in winners.items():
                following[winner] += probability * weight
            total_reads += probability * reads
            total_bounds += probability * bounds
            total_cuts += probability * cuts
        incumbents = following
    return incumbents, total_reads, total_bounds, total_cuts


def verify_figure_example(path):
    class Tape:
        def __init__(self, positions):
            self.positions = iter(positions)
            self.draws = 0

        def randrange(self, degree):
            position = next(self.positions)
            assert 0 <= position < degree
            self.draws += 1
            return position

    profile = ScoreProfile(1, 4, 0)
    adjacency = {"a": list(range(32)), "b": list(range(32, 64))}
    discovered_count = {"a": 26, "b": 16}
    total_eligible = {"a": 24, "b": 16}
    remaining_eligible = {"a": 2, "b": 12}
    discovered = set()
    eligible = set()
    for vertex, neighbors in adjacency.items():
        seen = discovered_count[vertex]
        useful = remaining_eligible[vertex]
        discovered.update(neighbors[:seen])
        eligible.update(neighbors[:total_eligible[vertex] - useful])
        eligible.update(neighbors[seen:seen + useful])
    tapes = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            vertex = row["candidate"]
            unseen = useful = 0
            samples = []
            for draw in range(1, 9):
                raw, observed = row[f"draw_{draw}"].split(":")
                position = int(raw)
                neighbor = adjacency[vertex][position]
                expected = "D" if neighbor in discovered else "E" if neighbor in eligible else "I"
                assert observed == expected
                unseen += observed != "D"
                useful += observed == "E"
                if draw == 4:
                    assert Fraction(*rate(32, 8, unseen + 4, useful + 4, profile)) == Fraction(row["after_four_maximum_rate"])
                samples.append(position)
            assert unseen == int(row["full_unseen"]) and useful == int(row["full_unseen_eligible"])
            assert Fraction(*rate(32, 8, unseen, useful, profile)) == Fraction(row["full_sampled_rate"])
            tapes[vertex] = samples
    results = []
    for window, expected_reads in ((("a", "b"), 16), (("b", "a"), 12)):
        full_tape = Tape(tapes[window[0]] + tapes[window[1]])
        cut_tape = Tape(tapes[window[0]] + tapes[window[1]])
        winner, full = choose(window, adjacency, discovered, eligible, full_tape, profile)
        cut_winner, bounded = choose(window, adjacency, discovered, eligible, cut_tape, profile, (4,))
        assert winner == cut_winner == "b"
        assert full_tape.draws == cut_tape.draws == 16
        assert full.positions == 16 and bounded.positions == expected_reads
        results.append({"native_first": window[0], "selected": winner, "full_reads": 16, "bounded_reads": expected_reads})
    return results


def main():
    here = Path(__file__).resolve().parent
    windows = {
        # The two candidates in Figure 1, using its displayed cost profile.
        "figure1_depleted_first": (ScoreProfile(1, 4, 0), [(6, 2), (16, 12)]),
        "figure1_productive_first": (ScoreProfile(1, 4, 0), [(16, 12), (6, 2)]),
        # Same four neighborhoods, same depletion and spread, different placement.
        "articles_productive_first": (ScoreProfile(), [(14, 10), (6, 2), (16, 4), (12, 1)]),
        "articles_productive_last": (ScoreProfile(), [(6, 2), (16, 4), (12, 1), (14, 10)]),
        # Little useful work left anywhere. An exact zero-yield window is a
        # constructive counterexample to any claim of unconditional savings.
        "articles_depleted": (ScoreProfile(), [(6, 1), (3, 1), (5, 1), (6, 0)]),
        "articles_zero_yield": (ScoreProfile(), [(6, 0), (3, 0), (5, 0), (6, 0)]),
    }
    rows = []
    for scenario, (profile, window) in windows.items():
        full_distribution, full_reads, _, _ = evaluate_window(window, (), profile)
        for checkpoints in budgets():
            distribution, reads, bounds, cuts = evaluate_window(window, checkpoints, profile)
            assert all(distribution[k] == full_distribution[k] for k in distribution.keys() | full_distribution.keys())
            assert reads <= full_reads
            saved = full_reads - reads
            rows.append({
                "window": scenario,
                "profile_a_b_c": f"{profile.a}/{profile.b}/{profile.c}",
                "native_order_u_y": " ".join(f"{u}/{y}" for u, y in window),
                "checkpoints": "+".join(map(str, checkpoints)) or "full",
                "positions": float(reads),
                "positions_saved": float(saved),
                "bound_checks": float(bounds),
                "stopped_candidates": float(cuts),
                "saved_positions_per_check": float(saved / bounds) if bounds else "",
            })
    with (here / "exact_probe_counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "prefix_suffix_pairs_checked": verify_upper_bound(), "windows": len(windows),
        "settings_per_window": len(budgets()), "rows": len(rows),
        "figure_1_draw_plan": verify_figure_example(here / "figure1_draws.csv"),
    }
    (here / "exact_probe_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
