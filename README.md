# SelFront: Scheduling Filtered Graph Search by Remaining Neighborhood Yield

This repository accompanies the paper with a readable reference operator, a small graph example, exact sampling calculations, configuration records, and tabulated paper results. Start with the [paper map](paper-map.md) to locate each figure and table.

## Browse the materials

- [Operator and API](docs/operator.md): query state, probe semantics, activation, stopping, and implementation boundaries.
- [Evaluation protocol](docs/protocol.md): cohorts, width selection, cost accounting, and adapter settings.
- [Data dictionary](data/README.md): files, units, denominators, and precision.
- [Reference implementation](src/selfront.py): actual adjacency traversal and vector distances.
- [Example input](examples/circle.json): 64 unit-circle vectors and a fixed adjacency graph.
- [Figure 1](figures/flow.pdf), [Figure 2](figures/local_probability.pdf), and [Figure 3](figures/depletion.pdf): paper figure snapshots.
- [Example results and traces](outputs/example.json): actual execution on the supplied small graph.
- [Exact probability output](outputs/probe_results.json): recomputed local sampling distributions and selection probabilities.
- [Archive arithmetic output](outputs/archive_summary.json): relative reductions calculated from displayed paper means.

## Run locally

Use Python 3.10 or later. All commands below use only the Python standard library, require no downloads, and run from this repository root.

```sh
python scripts/run_example.py
python scripts/validate.py
python scripts/exact_sampling.py
python scripts/analyze_archive.py
python scripts/check_selection.py
python scripts/analyze_contrasts.py
```

The example computes results and expansion traces for BPF and SelFront on the supplied graph. `validate.py` checks operator invariants and relationships among the archived tables. `exact_sampling.py` enumerates multinomial probabilities using exact rational arithmetic, including the 528 positive-yield states at degree 32. `analyze_archive.py` calculates reductions from the tabulated summaries. Generated files go to `outputs/`.

The reference operator accepts a supplied bottom-layer graph, predicate set, and entry vertex. It implements the scheduling mechanism and cardinality fallback. HNSW construction, upper-layer descent, a native pilot, application encoders, production kernels, and external adapters are outside this implementation. The scale-study CSVs are the paper's aggregate result archive; the example and analysis commands do not rerun those studies or produce their latency measurements. No source application snapshots or per-query benchmark traces are bundled.

The example's cost coefficients `(a,b,c)=(1,4,0)` are illustrative units shared with the local sampling calculation. They are not a timing calibration for the user's machine. The example reports operation counts and recall, not measured milliseconds or a speedup claim. To inspect a different supplied graph, pass `--input path/to/graph.json`; its schema and preconditions are described in [the operator guide](docs/operator.md).

## Decision settings and comparison summaries

[Workload cost profiles](data/cost_profiles.csv) fix rho=b/a and kappa=c/a in adjacency-entry units; the four collection-specific JSON configurations apply these ratios to the reference operator. The circle example retains its separate illustrative (1,4,0) profile. [Finite-grid selection](scripts/check_selection.py) checks weighted recall, per-bin floors, and the tuning-latency argmin, then writes [selected configurations](outputs/selection.json). [Paired contrast analysis](scripts/analyze_contrasts.py) calculates intervals from the archived run-mean summaries, with results in [contrast output](outputs/paired_contrasts.json). Both commands analyze supplied summaries, not new benchmark measurements.

[Adapter scalar rules](src/favor_rules.py) and [FAVOR-A settings](configs/favor_adapter.json) make the distance conversion, penalty and stopping predicate inspectable. These helpers do not implement the full external adapter. [Snapshot descriptors](data/snapshots.csv) identify the application collections and split keys; they are not public download endpoints.
