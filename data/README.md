# Data dictionary

CSV files are UTF-8 with header rows. They contain paper-level aggregates, not per-query traces. Numeric blanks mean an empty cohort or an inapplicable setting; they never mean zero latency. Recall is a fraction in [0,1]. All `_ms` fields use milliseconds. Latency tables report mean complete-request latency for the stated cohort; `cost.csv` reports additive mean cost components whose sum is the complete-request mean. A graph-routed cohort retains requests that later fall back to an exact scan. Selected comparisons also have paired run-mean contrast summaries; their intervals describe variation across five repetitions, not sampling a new query population.

| File | Fields and units | Scope |
|---|---|---|
| `collections.csv` | `collection` identifier; `records` count; `dimension` coordinates; `attribute_bytes` packed metadata bytes/record; `test_requests`, `graph_requests` counts | Table 1 |
| `main.csv` | `collection`; `{bpf,selfront}_graph_ms`, `_all_ms`; `{bpf,selfront}_graph_recall` mean recall@10 | Table 2; graph versus all requests |
| `articles_bins.csv` | `bin` 1–4 in increasing selectivity; `requests`, `graph_requests` counts; `exact_ms` exact-routed complement; `{bpf,selfront}_graph_ms`, `_all_ms`, `_graph_recall` | Table 3; Articles, 2500 requests/bin |
| `ablations.csv` | `variant`; `latency_ms`; `expansions` mean full adjacency expansions/request; `graph_distances` mean bottom-layer evaluations/request; `recall` mean recall@10 | Table 4; 3200 Articles graph requests; distance counts exclude pilot/fallback |
| `quality_points.csv` | `collection`, `method`; `target` pooled graph recall; `beta` dimensionless width multiplier; `tuning_recall`, `test_recall`; `test_ms` | Table 5; independently selected points on fixed cohorts |
| `adapter_settings.csv` | `adapter`, `collection` (`all` means shared); `scan_gate` selectivity fraction; `E` search control (Compass result-queue target); `variant`; `step`, `ei` Compass counts; `lambda` PF-R multiplier; `Lmax` returned-candidate cap | Table 6; see protocol guide for additional fixed controls |
| `external.csv` | `collection`; `{exact,pfr,acorn,navix,favor,compass,selfront}_ms` | Table 7; 10,000 requests/collection |
| `adapter_recall.csv` | `adapter`, `collection`; `bin1`–`bin4` mean recall@10 fractions | Table 8; equal 2500-request bins; Exact is 1 in all bins |
| `quartiles.csv` | `quartile` increasing native-trace depletion; `requests`; `median_depletion` fraction; `median_yield_spread` records; `bpf_ms`, `selfront_ms` | Figure 3; 800 Articles graph requests/quartile |
| `cost.csv` | `component`; `bpf_ms`, `selfront_ms` additive mean request costs | Section 6.4; Articles graph requests |
| `sensitivity.csv` | `parameter` experiment axis or named residency condition; `value` probe/window count, or 1 marking the named condition; `collection`, `cohort`; `latency_ms` | Section 6.5; graph cohort throughout |
| `local_probabilities.json` | `wide`, `depleted`: lists of `s` (probe budget), `choose_second` probability, `true_scores` and `mean_scores` (eligible records/cost unit), `expected_local_regret` (same rate unit) | Section 4 and Figure 2; candidate order is nearer first |

## Precision and aggregation

Table CSVs preserve displayed precision. The Articles Table 2 graph means 3.244/2.647 are rounded from 3.24375/2.646875, obtained from Table 3's 1400/1800 weights. Its displayed graph recalls .9638/.9623 derive from .9638125/.96225; the bin recalls also have display rounding. `validate.py` allows the relevant half-unit rounding tolerance when comparing these fields.

The quartile archive retains 2.9025 for the fourth SelFront group, displayed as 2.903 in the text, to retain the exact weighted mean. The cost archive retains .30375 and .206875 queue costs for the same reason. Scheduler cost .180 comprises .035 duplicate-eligibility counter work, .103 sampling, and .042 window processing. `analyze_archive.py` uses Table 2's displayed values, so its percentage outputs may differ slightly from calculations with unrounded means.

Local sampling uses degree 32 and (a,b,c)=(1,4,0). The wide pair is (U,Y)=(6,2),(16,12); its true winner is the second candidate. The depleted pair is (2,2),(16,4); its true winner is the first. Ties favor the nearer first candidate. At s=32 the implementation uses the exact-count branch, so this point is not a 32-draw replacement estimate. The JSON is an archived exact calculation; `scripts/exact_sampling.py` recomputes it into `outputs/` with exact fractions internally.

## Additional decision and contrast records

- `cost_profiles.csv`: collection, dimension, normalized a=1, `b_over_a` (rho), `c_over_a` (kappa). Ratios express processing work in adjacency-entry units and are fixed per collection.
- `tuning_grid.csv`: collection/method/beta; `tuning_ms`; graph and bin-3/bin-4 request counts; each bin recall, pooled recall and minimum bin recall. All rows are tuning-set graph-cohort summaries.
- `selected_test_bins.csv`: collection/target/method/beta; test graph and bin counts; bin and pooled recall; test complete-request milliseconds. These are the selected points, including Table 5 display rounding.
- `sensitivity_quality.csv`: parameter/value; collection/cohort; latency; graph/bin counts; bin and pooled recall for the six probe/window points.
- `paired_contrasts.csv`: collection/configuration/comparison, repetitions=5, mean paired difference in milliseconds, and `se_run_mean_ms`, the sample SD of the five paired run means divided by sqrt(5). Each run mean averages matched requests; a positive BPF-minus-SelFront value favors SelFront. A 95% Student interval uses mean +/- 2.7764451052*SE with four degrees of freedom. Repeated runs are not treated as additional independent queries. These summary records contain no individual timing logs.
- `snapshots.csv`: collection and snapshot identifier, cutoff date, record/split keys, record count and vector dimension. Identifiers are application descriptors, not third-party benchmark names or hosting URLs.

The tuning counts are 640 Articles graph requests (280/360 by bin) and 580 Media graph requests (300/280). Selected test counts are 3200 (1400/1800) and 2900 (1500/1400). Recalls are decimal summary values, not integer hit-count files; small display differences are handled with explicit rounding tolerances.
