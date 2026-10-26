# Paper-to-material map

Numbering follows the accompanying SelFront paper.

| Paper item | Material | What can be inspected or executed |
|---|---|---|
| Section 2: C/W/R/D and native bounds | [operator source](src/selfront.py), [operator guide](docs/operator.md) | Supplied graph traversal; bounded heaps; ineligible bridges; independent result admission |
| Section 3: fresh probes, yield/cost, activation | [operator source](src/selfront.py), [configuration](configs/operator.json) | Read-only replacement probes, exact small lists, distance window, native period, occurrence gate |
| Figure 1: remaining-work choice | [snapshot](figures/choice.pdf), [example runner](scripts/run_example.py) | View diagram; inspect actual step-by-step JSON trace from a small graph |
| Section 4 and Figure 2 | [exact enumeration](scripts/exact_sampling.py), [probabilities](data/local_probabilities.json) | Recompute distribution means, bias checks, and pair-selection probabilities |
| Table 1 | [collections](data/collections.csv) | Collection dimensions, counts and graph-route denominators |
| Table 2 | [main results](data/main.csv), [archive analysis](scripts/analyze_archive.py) | Calculate graph/all-request relative reductions |
| Table 3 | [Articles bins](data/articles_bins.csv), [validation](scripts/validate.py) | Recompute weighted all-request and graph means |
| Table 4 | [ablations](data/ablations.csv) | Compare numerator, cost and reordering controls |
| Table 5 | [selected quality points](data/quality_points.csv), [protocol](docs/protocol.md) | Inspect selected beta, tuning/test recall and latency; finite tuning grid and bin constraints are bundled |
| Table 6 | [adapter settings](data/adapter_settings.csv), [protocol](docs/protocol.md) | Inspect routing, search and fixed adapter parameters |
| Table 7 | [external latency](data/external.csv) | All-request adapter comparison |
| Table 8 | [adapter recall](data/adapter_recall.csv) | Per-bin quality; preserve different exact-scan policies |
| Section 6.4 cost accounting | [cost components](data/cost.csv), [validation](scripts/validate.py) | Sum costs and check against weighted graph means |
| Figure 3 | [matched strata](data/matched_strata.csv), [figure](figures/opportunity.pdf), [calculation](scripts/check_opportunity.py) | Separate saved host work, scheduling cost and net saving by request-level opportunity |
| Section 6.5 | [sensitivity/residency](data/sensitivity.csv) | Probe/window costs and cold-versus-warm reversal |

All archived fields and rounding rules are defined in the [data dictionary](data/README.md). Executable examples cover the scheduling mechanism and exact local probability calculation. Scale-study latencies and external adapters are provided as configuration/result records.

| Additional paper detail | Material | Check |
|---|---|---|
| Section 3.2 and 5.3 normalized costs | [profiles](data/cost_profiles.csv) | Reconstruct rho/kappa scoring |
| Section 5.3 / Table 5 selection | [grid](data/tuning_grid.csv), [test bins](data/selected_test_bins.csv), [selection script](scripts/check_selection.py) | Feasibility and argmin |
| Section 6.3 paired contrasts | [summaries](data/paired_contrasts.csv), [analysis](scripts/analyze_contrasts.py) | Run-mean Student intervals |
| Section 6.5 quality conditions | [sensitivity quality](data/sensitivity_quality.csv) | Per-bin and pooled recall |
| Section 6.6 FAVOR-A | [configuration](configs/favor_adapter.json), [scalar helpers](src/favor_rules.py) | Euclidean penalty scale and stopping predicate |

| New paper item | Material | Check |
|---|---|---|
| Section 3.5 host composition | [interface](src/host_window.py), [host guide](docs/host-composition.md) | Host-native keys, stopping and read-only window choice |
| Section 4.3 native-relative opportunity | [exact decision](outputs/exact_window_check.json) | Same neighborhood states with opposite native orders |
| Table 9 / Section 6.6 | [host results](data/host_composition.csv), [paired contrasts](data/host_contrasts.csv) | Fixed host settings, per-bin recall and additional savings |

The earlier depletion quartiles remain available as [an auxiliary decomposition](data/quartiles.csv); Figure 3 uses the matched request strata. Table 3 displays the graph columns of the full bin archive, rounded to four recall decimals.

| Section 5.3 relative-cost mismatch | [calculation](scripts/check_profile_mismatch.py), [output](outputs/profile_mismatch.json) | Five scoring profiles, fixed evaluation cost, exact and sampled choices |

Independent host-width selection in Section 6.6 uses [the candidate grid](data/host_tuning_grid.csv), [selected test bins](data/host_selected_test.csv), and [the selection check](scripts/check_host_tuning.py).
