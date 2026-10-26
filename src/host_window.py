"""Read-only selection interface for a host-owned frontier and expansion loop."""
import math
from selfront import probe


def choose_expansion(frontier, adjacency, discovered, eligible, rng, cfg,
                     *, host_stopped=False, expansion_bound=math.inf,
                     enabled=True, completed_steps=0):
    """frontier: (nonnegative native key, ID) pairs; return ID and probe count.

    Caller evaluates the host stopping predicate before this call and supplies
    its currently admissible expansion bound (infinity when open). This routine
    changes no frontier, discovered set, heap, or result. The caller performs
    the chosen full expansion with its own admission and result policy.
    """
    if host_stopped or not frontier:
        return None, 0
    ordered = sorted(frontier)
    if any(not math.isfinite(p) or p < 0 for p, _ in ordered):
        raise ValueError('host keys must be finite and nonnegative')
    if len({v for _, v in ordered}) != len(ordered):
        raise ValueError('frontier IDs must be distinct')
    native_key, native = ordered[0]
    if native_key > expansion_bound:
        raise ValueError('continuing host must allow its native minimum')
    if not enabled or (completed_steps + 1) % cfg.h == 0:
        return native, 0
    cap = min(expansion_bound, (1 + cfg.epsilon) * native_key + cfg.tau)
    window = [(p, v) for p, v in ordered[:cfg.w] if p <= cap]
    if len(window) < 2:
        return native, 0
    scored, reads = [], 0
    for p, v in window:
        _, _, score, n = probe(adjacency[v], discovered, eligible, rng, cfg)
        scored.append((-score, p, v))
        reads += n
    return min(scored)[2], reads
