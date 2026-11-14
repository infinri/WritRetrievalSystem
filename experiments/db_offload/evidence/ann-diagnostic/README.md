# Supplemental ANN load diagnostic

Exploratory diagnostic registered after the primary evaluation, before implementation/execution at commit 2f2729b2459b5c0eef1b73e4b4f9be4de48fa395. Fixed HNSW parameters came from the pre-existing oracle profile, with no tuning or held-out scoring. This is a separate local host: never substitute its timings for the primary hosted run. All three arms share this host and inputs.

| Arm | Active readers | Status | Samples | E2E p50 / p95 / p99 ms | Peak RSS MiB |
|---|---:|---|---:|---|---:|
| A-exact | 1 | COMPLETE | 1000 | 130.5/164.2/190.7 | 555.3 |
| D-native | 1 | COMPLETE | 1000 | 56.8/75.1/104.9 | 1869.8 |
| A-exact | 4 | COMPLETE | 1000 | 723.2/970.5/1046.6 | 619.4 |
| D-native | 4 | COMPLETE | 1000 | 76.6/117.2/154.8 | 1863.7 |
| A-ANN | 1 | COMPLETE | 1000 | 106.3/127.5/139.8 | 591.4 |
| A-ANN | 4 | FAILED | 956 | - | 632.7 |

Five profiles completed 1,000 samples; A-ANN/four readers exceeded the registered 180-second query limit. No adoption percentiles are reported for that failed profile. Exact/calibration and native source policies remain unchanged.

A-ANN single-reader p95 is 127.5 ms versus A-exact 164.2 ms and native Neo4j 75.1 ms. ANN did not erase the observed load advantage of native candidate processing. This is not a same-answer-quality victory: no new semantic labels were scored, and the primary Neo4j profile failed the registered quality gate.

Four cached development vectors have strict exact-oracle recall .90/1.00/.90/1.00 and tie-aware recall 1.00 each. These near-duplicate synthetic-vector results are not semantic relevance or held-out quality evidence. ANN ordering is deterministic within its returned set, without a global exact-tie guarantee.

The flat control deliberately retains Writ/Tantivy full permitted-hit materialization for global lexical ties. At larger size its stored-document extraction/fusion overhead is still substantial; this does not prove all optimized flat designs slower. Inference, complete rendering, fixed visibility, RRF, CPU/RSS and all failures remain counted. Shared-host conditions and uncontrolled OS caches limit extrapolation.

The supplemental result changes no primary outcome, architecture adoption, claim/evidence semantics or production code. Further quality tuning requires a new held-out set and actual independent review.
