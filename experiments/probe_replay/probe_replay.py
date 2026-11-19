"""Checkpoint pruning of an unchanged, fixed-budget score."""

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class ScoreProfile:
    a: int = 1
    b: int = 10
    c: int = 2
    samples: int = 8


@dataclass
class ProbeWork:
    positions: int = 0
    draws: int = 0
    bounds: int = 0
    cuts: int = 0
    impossible_at_entry: int = 0

    def add(self, other):
        self.positions += other.positions
        self.draws += other.draws
        self.bounds += other.bounds
        self.cuts += other.cuts
        self.impossible_at_entry += other.impossible_at_entry


def rate(degree, budget, unseen, eligible, profile):
    """Integer numerator/denominator of the existing score."""
    if degree == 0:
        return (0, 1)
    return (
        degree * eligible,
        budget * (profile.c + profile.a * degree) + profile.b * degree * unseen,
    )


def beats(left, right):
    return left[0] * right[1] > right[0] * left[1]


def choose(window, adjacency, discovered, eligible, rng, profile, checkpoints=()):
    """Native-ordered IDs, immutable state, equal RNG advancement.

    'positions' counts an adjacency entry and the two bitmap memberships read
    for that slot. The archived full scorer reads both bitmap values per slot.
    """
    if not window:
        raise ValueError("a decision requires a nonempty native window")
    if tuple(sorted(set(checkpoints))) != checkpoints or any(
        n <= 0 or n >= profile.samples for n in checkpoints
    ):
        raise ValueError("checkpoints must be sorted interior sample counts")

    winner = window[0]
    best = (0, 1)
    work = ProbeWork()
    for rank, vertex in enumerate(window):
        neighbors = adjacency[vertex]
        degree = len(neighbors)
        sampled = degree > profile.samples
        budget = profile.samples if sampled else degree
        unseen = useful = 0
        for slot in range(budget):
            position = rng.randrange(degree) if sampled else slot
            neighbor = neighbors[position]
            fresh = neighbor not in discovered
            accepted = neighbor in eligible
            unseen += int(fresh)
            useful += int(fresh and accepted)
            work.positions += 1
            if sampled and rank and slot + 1 in checkpoints:
                remaining = budget - slot - 1
                upper = rate(degree, budget, unseen + remaining, useful + remaining, profile)
                work.bounds += 1
                # This offline diagnostic costs an extra comparison in the
                # checker, and is not part of the tested selection policy.
                smallest_upper = rate(degree, budget, budget, remaining, profile)
                work.impossible_at_entry += int(beats(smallest_upper, best))
                if not beats(upper, best):
                    work.cuts += 1
                    # Advance the same generator even though no suffix IDs or
                    # bitmaps are accessed. Subsequent windows see the same RNG.
                    for _ in range(remaining):
                        rng.randrange(degree)
                    break
        else:
            score = rate(degree, budget, unseen, useful, profile)
            if beats(score, best):
                best, winner = score, vertex
        if sampled:
            work.draws += budget
    return winner, work


def count_states(draws):
    return [(unseen, useful) for unseen in range(draws + 1) for useful in range(unseen + 1)]


def verify_upper_bound():
    """Check every count prefix and suffix for several paper profiles."""
    count = 0
    for profile in (ScoreProfile(1, 4, 0), ScoreProfile(), ScoreProfile(1, 18, 2)):
        for degree in (9, 16, 32, 64):
            for prefix in range(profile.samples):
                remaining = profile.samples - prefix
                for unseen, useful in count_states(prefix):
                    upper = rate(degree, profile.samples, unseen + remaining, useful + remaining, profile)
                    for tail_unseen, tail_useful in count_states(remaining):
                        observed = rate(
                            degree, profile.samples,
                            unseen + tail_unseen, useful + tail_useful, profile,
                        )
                        assert not beats(observed, upper)
                        count += 1
                    assert beats(upper, rate(degree, profile.samples, unseen, useful, profile))
    return count


def budgets():
    return [()] + [(n,) for n in (4, 5, 6, 7)] + list(combinations((4, 5, 6, 7), 2))
