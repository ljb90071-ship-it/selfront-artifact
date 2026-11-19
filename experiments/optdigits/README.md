# OptDigits paired graph-query probe counts

The experiment pairs full and bounded probes on the same requests and random streams. The graph traversal follows the supplied SelFront reference operator with a single-layer exact 32-nearest-neighbor graph and a fixed entry and width.

## Source and environment

E. Alpaydin and C. Kaynak (1998), *Optical Recognition of Handwritten Digits*, UCI Machine Learning Repository, DOI 10.24432/C50P49. UCI lists the dataset under CC BY 4.0. Save the archive from the UCI download endpoint and pass its location to the runner. The script uses only `optdigits.tra` and `optdigits.tes` and verifies the archive SHA-256. [Dataset and citation](https://doi.org/10.24432/C50P49), [UCI archive](https://archive.ics.uci.edu/static/public/80/optical+recognition+of+handwritten+digits.zip), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The source split contains handwritten samples from 30 writers in the training file and 13 different writers in the test file. The run indexes all 3,823 training vectors and queries all 1,797 test vectors, each 64-dimensional. All feature vectors were unique within each split and disjoint across splits. Original digit labels are retained. Windows 11 build 26300, AMD Ryzen 9 9955HX, Python 3.14.5, NumPy 2.4.6, with one OpenBLAS thread configured for offline graph construction.

## Protocol

- Build a directed graph with the 32 nearest other training records per vertex, ordering by squared Euclidean distance and then source row ID. Search starts at the training record minimizing the sum of squared distances to all training records, with row-ID tie-breaking. All 3,823 vertices are reachable from this entry. Search uses width `ef=64`, result size `k=10`, and a native distance stopping rule. Query-to-record distances are calculated at discovery. The same graph, entry, width, and stop condition apply to all methods. If the graph returns fewer than 10 eligible IDs, the method scans its eligible set exactly.
- For each test vector, run bitmap predicates for matching its digit, matching its parity, and matching the opposite parity against the training labels. Use the same prebuilt bit-packed selection bitmap per predicate value for all methods. Exhaustive squared-distance ordering of the eligible training rows, with row ID as the tie-break, supplies ground truth independently of the graphs and schedulers.
- Native pops the minimum of the distance-ordered pending heap. Full sampling evaluates up to four pending candidates within both the native stop bound and 1.1 times the native-first squared distance. Each candidate gets eight uniform positions with replacement. Eight initial native expansions supply the overlap gate, with updates every 64 expansions thereafter. Activate when there are at least 32 eligible adjacency occurrences and at least 35% of them are already discovered. Every fourth expansion is native. The score uses `(a,b,c)=(1,4,2)`.
- Lazy evaluates the native-first candidate fully and then scores candidates in increasing `(squared distance, row ID)` order. Check the upper bound after positions 4 and 6 and skip the rest when the bound is at most the best completed score. The earlier candidate wins an exact tie. All planned positions are drawn in both variants using `random.Random((replicate << 32) | test_row_id)` for replicate IDs 0, 1, and 2. Skipping reads consumes the same random stream and avoids the associated adjacency ID and state accesses.

For a degree d and budget s, let u and y be the unseen and eligible counts at a checkpoint, with m draws outstanding. The upper bound uses y+m in the numerator and u+m in the denominator. The scorer compares integer cross-products and retains the earlier native candidate on a tie, including where candidate keys tie and row ID supplies their order.

## Run and read the results

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
python -B experiments/optdigits/run.py --archive PATH_TO_UCI_ZIP
```

Add `--write` to regenerate `results.json` and `per_request.csv.gz`. Run from the artifact root with the downloaded archive, NumPy and Python. The optional argument `--reference PATH_TO_SELFRONT_PY` checks the first three test vectors, each of the three predicates, and all three methods at replicate zero against the designated release reference. The recorded run passed 27 such checks of choices, result IDs, and counters, including the number of lazy bound checks. The reference module SHA-256 is in the JSON.

To obtain the dataset independently, download the official UCI archive to `optdigits-uci.zip` in this directory. Its SHA-256 is `0d7b054fea010270e9b3f06411c654c5e59547732ad626381980baffe0a23fb0`. Run `Get-FileHash -Algorithm SHA256 -LiteralPath optdigits-uci.zip` to verify it separately. [Official UCI archive](https://archive.ics.uci.edu/static/public/80/optical+recognition+of+handwritten+digits.zip).

Each row of the compressed CSV is one query, predicate, and replicate. There are 5,391 unique query–predicate pairs and 16,173 full/lazy comparisons. Native runs once per pair, and its measurements appear on all three replicate rows for pairing. Each comparison asserts equality of full and lazy windows, expansion paths, final ordered IDs, RNG states, and graph and fallback work. Recall uses the fraction of exact top-10 IDs retrieved. The JSON also reports recall counts on rows where both native and the paired scheduler returned 10 results from the graph and used no exact fallback.

A probe read means an adjacency position whose ID and state are inspected, counting repeated positions as repeated reads. Probe reduction divides skipped positions by full-sampler probe reads for that group. The window denominator contains only steps that actually sampled at least two candidates. The active-row denominator contains only query–predicate–replicate rows with at least one such window. The seed sensitivity counts unique query–predicate pairs whose paths or answers differ across the three seeds. The measurements cover adjacency positions and distance work in the fixed graph invocation.

| Predicate | Native recall@10 | Full/lazy recall@10 | Full probe reads | Lazy probe reads | Reads saved | Sampled windows with no saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Same digit | 0.99878 | 0.99878 | 2,733,256 | 2,684,898 | 1.77% | 75,332 / 89,453 |
| Same parity | 0.99065 | 0.99123 | 4,080,200 | 3,983,362 | 2.37% | 107,379 / 134,134 |
| Opposite parity | 0.75676 | 0.76012 | 3,303,432 | 3,271,494 | 0.97% | 99,978 / 107,463 |
| Pooled | 0.91540 | 0.91671 | 10,116,888 | 9,939,754 | 1.75% | 282,689 / 331,050 |

Of the 16,173 rows, 9,648 reached a sampled window and 2,445 of those saved zero probe reads. The pooled decrease was 177,134 positions, including 13,739 candidate tails skipped after four observed positions and 61,089 after six. There were 1,853,383 bound checks and 48,105 cutoffs at exact equality. Full and lazy each drew 10,116,888 positions and performed 6,554,975 graph distance evaluations and 2,419,029 fallback distance evaluations. The pooled native run total on the same repeated denominators was 37,925,568 expansion-adjacency reads. Lazy used 47,849,034 positions across its expansions and probes, up 26.17%. The corresponding full total was 48,026,168, so lazy reduced their combined position count by 0.37%.

Changing the sampling seed changed the expansion path in 2,819 of the 5,391 query–predicate pairs and the answer in 67 pairs. Relative to native, the two samplers improved recall on 128 rows and lowered it on 56. For opposite parity, the three methods each fell back on the same 1,227 of 5,391 rows. On the remaining 4,164 rows, native and the samplers achieved 0.68509 and 0.68943 recall@10, respectively. The probe certificate preserved the sampled decision in all runs, including this lower-recall cohort.

## Manuscript citation

```bibtex
@misc{alpaydin1998optdigits,
  author = {Alpaydin, E. and Kaynak, C.},
  title = {Optical Recognition of Handwritten Digits},
  year = {1998},
  howpublished = {UCI Machine Learning Repository},
  doi = {10.24432/C50P49}
}
```
