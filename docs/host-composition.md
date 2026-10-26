# Composing with a host priority

The host owns the candidate key, stopping condition, expandable bound, discovery set, admission, full expansion and result extraction. SelFront chooses one pending expansion after the host has tested stopping at its original minimum. `choose_expansion` takes `(key, ID)` frontier entries, adjacency, discovery and eligibility sets, a random generator and the same scheduler configuration as the distance-ordered operator. It returns an ID and metadata-read count. It leaves input state unchanged.

For FAVOR-A, the key is Euclidean distance plus the ineligible-candidate penalty. The scalar rule is in `favor_rules.py`. The worst search-heap key bounds expansions only when the heap is full and its eligible fraction exceeds .5; otherwise the host supplies an infinite bound. The window uses the first four keys within 1.1 times the native minimum plus 1e-6. Every fourth expansion uses the current native minimum. Ties use native key then ID. The host retains eligible answer extraction from its own width-E search heap.

`check_host_composition.py` exercises this selection interface using supplied neighborhoods, including a continuing host with an open bound. The core `selfront.search` runner continues to implement the distance-ordered host. Collection-level FAVOR combinations are specified by `configs/host_composition.json`, `data/host_composition.csv` and `data/host_contrasts.csv`.

The four methods share each collection's frozen FAVOR-A E, gate, penalty, graph and completion policy. Eligible-first selects the smallest-key eligible window member (the minimum if none qualifies). Shuffled-score permutes the sampled scores before choice. Both use the same overlap gate, bounded window and periodic native steps. Complete-request times include the scheduling work and any exact completion. Each row reports all four selectivity-bin recalls. The paired intervals use five run means and a t4 multiplier of 2.7764451051977987.

FAVOR source: https://arxiv.org/html/2605.07770v1, Algorithm 3 and Sections 5.1–5.4. Neighborhood-state scheduling is the additional choice described here.
