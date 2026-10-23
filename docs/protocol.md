# Evaluation configuration and interpretation

The [protocol configuration](../configs/protocol.json) records the paper's fixed routing and tuning parameters. [Operator settings](../configs/operator.json) instantiate the reference example. The default circle profile is illustrative. Collection-specific profiles fix (a,b,c)=(1,4,2), (1,10,2), and (1,18,2) for 128, 384, and 768 dimensions in adjacency-entry cost units; these are scoring specifications, not nanosecond measurements. Profiles remain fixed across width and s/w comparisons.

Each collection has 2,000 tuning requests and 10,000 disjoint test requests. Four equal-size test bins are [0.01,0.1)%, [0.1,1)%, [1,10)%, and [10,50]%. Vectors are normalized float32 and distance is squared Euclidean. Catalog/Catalog-L use CLIP ViT-B/32 projected from 512 to 128 dimensions; Articles uses all-MiniLM-L6-v2 (384); Media uses CLIP ViT-L/14 (768). Corpus construction, joins, and source snapshots are specified in Section 5 of the paper; the repository bundles aggregate results and the separate small operator input.

The common policy scans exactly if cardinality is below k or selectivity is below .01. Otherwise a native unfiltered width-128 pilot supplies eligibility among its final best 128 records. Fewer than eight eligible records triggers scanning. Remaining requests use `ef=next_power_of_two(max(256,beta*k/sigma))`, with widths above 16384 routed to exact scanning. The graph branch restarts from the pilot's bottom-layer entry with fresh state. Its cohort is fixed before scheduling; later cardinality fallbacks remain in that cohort. Complete-request latency includes predicate preparation, state reset, pilot, graph attempts, fallback, and result materialization.

The shared-width comparison chooses beta=4 from {2,4,8,16} using a common .95 recall floor in each graph-eligible bin. Independently tuned points choose the least tuning latency among beta values {2,2.5,3,3.5,4,5,6,8}, subject to the target pooled recall and .95 in each graph-eligible bin; ties choose lower beta. The archive includes the finite tuning grid, selected test-bin records, and sensitivity quality fields. No test-set interpolation is used. Media's independently tuned points reverse its shared-width latency advantage.

All record HNSW graphs use M=16, construction width 200, and maximum bottom degree 32. The scale protocol describes one pinned core, five repetitions, and warm residency. These settings describe the paper's result protocol, not a required platform for the Python example. The example does not implement SIMD distance kernels or benchmark latency.

## External adapter records

[Selected settings](../data/adapter_settings.csv), [all-request latency](../data/external.csv), and [bin recall](../data/adapter_recall.csv) correspond to Tables 6–8. E denotes graph search width except for Compass-A, where it is the result queue target. The labels describe common-engine adapter configurations, not remeasurements of the original publications. External adapters are configuration records here, not executable implementations.

PF-R uses lambda=4, starts at `min(16384,next_power_of_two(max(128,lambda*k/sigma)))` returned candidates, and searches at twice this width. It doubles the requested candidates on restart until 2k eligible records are available or the cap triggers exact completion. Cardinality below 2k scans directly. ACORN-A's gamma option uses gamma=16 and M_beta=32. NaviX-A uses adaptive-local expansion, leniency 3, and cutoff .5. FAVOR-A supplies exact selectivity to the exclusion rule; its Euclidean penalty, width normalization, score admission and stop predicate are specified in `configs/favor_adapter.json` and implemented as scalar helpers in `src/favor_rules.py`. The square root precedes the penalty; the final result ordering uses unmodified distance. Compass-A uses 4096 clusters, scalar B-trees, centroid HNSW M=16/construction width 200/step 32, and neighbor cutoffs .3/.05. Its graph-search increment (`step`) and relational batch size (`ei`) appear in the CSV; it has no direct scan gate or cardinality completion.

The adapter tuning grids use scan gates {0,.001,.01}, powers of two from 128 through 4096 for E, both ACORN variants, and {32,64,128} Compass step/batch settings. PF-R tests lambda in {2,4,8} and caps {4096,8192,16384}. Selection minimizes full-workload tuning latency with mean recall at least .95 in every selectivity bin.

## Archived quantities

Articles has 3200 graph requests (1400 and 1800 in the two upper bins), with seven BPF and five SelFront cardinality fallbacks. The graph cohort includes 2340 positive, 790 weak, and 70 adverse correlation requests. Approximate-only recalls are .9637/.9622 after removing the exact fallback outputs. The two low-selectivity bins remain in all-request denominators.

The quartiles are formed separately within native-trace selectivity bins then combined, giving 800 requests each. Depletion and yield spread covary; this partition supports an association, not an isolated causal estimate. The local probability calculation instead conditions on a fixed graph/discovery state and enumerates independent samples exactly. Those are different forms of analysis.

## Paired contrast summaries

The five repetitions use the same requests within each method pair and alternating method order after a disjoint warmup. The independent unit for the reported Student intervals is a paired run mean, not every repeated query execution. `paired_contrasts.csv` stores the mean difference and its run-level standard error. Articles target .960/.970 intervals stay positive; Media and fixed-versus-fresh intervals span zero and do not establish an ordering or equivalence.
