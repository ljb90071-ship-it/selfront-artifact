# Probe work in Sections 3.3 and 6.6

The full scorer draws up to eight neighbor positions per candidate. For lists of
degree above eight, draws are with replacement. Grouping repeated positions
reads each distinct slot once and credits its multiplicity to both counts.
The estimate always divides by the planned draw count. Grouping is local to
one candidate list and keeps at most eight position counts at the default
budget.

An ordered window evaluates its first candidate in full. At a checkpoint in a
later candidate, let H count eligible unseen draws, K count all unseen draws,
and m count unresolved draws. If d is the degree and L the planned sample
length, define delta = d/L. The upper bound is
delta*(H+m)/(c+a*d+b*delta*(K+m)). The optimistic tail treats each unresolved
draw as unseen and eligible. This maximizes the possible score because H <= K
and c+a*d is positive. A strict win is needed to displace an earlier
candidate. When the bound is at most the completed best score, the remaining
metadata accesses can be skipped. Any planned random draws still advance the
query generator. Expansion and answer equivalence uses the same starting
state, native tie order, probe stream, and state-based host stopping rule.

The reference supports full scoring for any existing profile. Its optimized
checkpoints use bounded integer cost coefficients and a power-of-two draw
budget so the intermediate scores used by the bound are exact before division.
The paired calculation also checks small exact scans and equal score ties.
Stable adjacency and bitmap state are required throughout each window.
The probe_reads field counts adjacency positions inspected, each with the
accompanying state lookups. Draws, bounds, and host expansions are separate work.

## Exact calculations and paired replay

Run from the artifact root. The exact calculations use Python's standard
library. The FAVOR-A fixture also uses NumPy.

    python scripts/check_probe_bounds.py
    python experiments/probe_replay/exact_probe.py
    python experiments/probe_replay/favor_replay.py
    python experiments/probe_replay/favor_replay.py --reuse-core src/selfront.py

The [exact enumeration](../experiments/probe_replay/exact_probe_counts.csv)
computes expected reads for two- and four-candidate windows. The
[draw plan](../experiments/probe_replay/figure1_draws.csv) instantiates Figure 1
with a native-first incumbent and an upper bound on the challenger. Its output
is in [exact_probe_summary.json](../experiments/probe_replay/exact_probe_summary.json).

The generated fixture is a degree-32 graph of 2,048 normalized vectors,
with 28 nearest links and four randomly placed links per row. The replay uses
24 query–predicate pairs, two seeds, and four widths. The predicate cases range
in selectivity from about .7% to 36%. The fixture applies the FAVOR-A key,
admission, stopping, and completion rules, and reuses precomputed query
distances to count work. It verifies full versus bounded path, discovery
updates, the RNG stream, and ordered answers, with exhaustive filtered
ground truth. It records 576 comparisons for the three ungrouped checkpoint
variants and 384 comparisons for reuse and reuse with a cutoff. See the
[checkpoint summaries](../experiments/probe_replay/favor_replay_summary.json)
and [grouped summaries](../experiments/probe_replay/favor_reuse_replay_summary.json).
The corresponding request CSVs hold per-request counts, and the window CSVs
hold counts by exact native-choice state. Table 6 uses marginal_cutoff_by_state
and divides additional reads avoided by physical reads after grouping. The
lower bound on any checkpoint's optimistic score is delta*m/(c+(a+b)*d).
Incumbents below this floor cannot prune at that checkpoint.

The [OptDigits experiment](../experiments/optdigits/README.md) uses the UCI
writer split and original digit labels. Its [results](../experiments/optdigits/results.json)
and compressed per-request CSV compare complete probe reads with checks at four
and six draws. The runner verifies the source archive hash and takes its local
path as an argument. The replay and OptDigits outputs are work counts. The
application benchmark tables use a separate complete-request timing protocol.
