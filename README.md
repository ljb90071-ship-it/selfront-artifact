# SelFront: Scheduling Filtered Graph Search by Remaining Neighborhood Yield

SelFront schedules filtered graph search by the eligible neighborhood work
that remains, using query-state observations to choose the next expansion.
Explore the mechanism through traversal traces, exact sampling calculations
and paper result tables; the [paper map](paper-map.md) connects each result to
its supporting material.

## Navigate

- [Operator and API](docs/operator.md): query state, probe semantics, activation, stopping and input preconditions.
- [Evaluation protocol](docs/protocol.md): cohorts, width selection, cost accounting and adapter settings.
- [Data dictionary](data/README.md): files, units, denominators and precision.
- [Implementation](src/selfront.py): adjacency traversal, vector distances, scheduling and cardinality fallback.
- [Example input](examples/circle.json): 64 unit-circle vectors and an adjacency graph.
- Figures: [operator flow](figures/flow.pdf), [local probability](figures/local_probability.pdf), and [depletion](figures/depletion.pdf).
- Outputs: [search traces](outputs/example.json), [sampling probabilities](outputs/probe_results.json), and [table comparisons](outputs/archive_summary.json).

## Run

Use Python 3.10 or later and its standard library. Run from the repository root:

```sh
python scripts/run_example.py
python scripts/validate.py
python scripts/exact_sampling.py
python scripts/analyze_archive.py
python scripts/check_selection.py
python scripts/analyze_contrasts.py
```

`run_example.py` computes BPF and SelFront results and expansion traces on the
supplied graph. The operator takes vectors, bottom-layer adjacency, a predicate
set and an entry vertex. Pass `--input path/to/graph.json` to use another input;
the [operator guide](docs/operator.md) defines the schema. Outputs report operation
counts and recall. The circle example uses `(a,b,c)=(1,4,0)` in adjacency-entry
cost units.

`validate.py` checks operator invariants and relationships among result tables.
`exact_sampling.py` uses rational arithmetic to enumerate multinomial
probabilities, including all 528 positive-yield states at degree 32. Generated
files go to `outputs/`.

## Analyze decisions and comparisons

`analyze_archive.py` calculates relative reductions from aggregate table means.
[Finite-grid selection](scripts/check_selection.py) checks weighted recall,
per-bin floors and the tuning-latency argmin, writing
[selected configurations](outputs/selection.json). [Paired contrast analysis](scripts/analyze_contrasts.py)
calculates intervals from run-mean summaries and writes
[contrast results](outputs/paired_contrasts.json).

[Workload cost profiles](data/cost_profiles.csv) define `rho=b/a` and `kappa=c/a`;
the collection-specific JSON configurations apply these ratios to the operator.
[Adapter scalar rules](src/favor_rules.py) and [FAVOR-A settings](configs/favor_adapter.json)
specify distance conversion, penalty and stopping. [Snapshot descriptors](data/snapshots.csv)
identify collections and split keys. The [evaluation protocol](docs/protocol.md)
connects these settings to the aggregate latency and recall tables.
