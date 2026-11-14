# Architecture bake-off: proposed decision

**Retain Relate persistence and the application retrieval/reliability baseline.**
The tested native profiles do not meet the registered adoption gates. No production
code/dependency is removed, no Rust rewrite is justified by these measurements,
and no architecture replacement is adopted. This is a measured experimental
result, not a general limit of databases, Rust or later engine versions.

## Primary execution and quality

Primary hosted replication: [43540148638](https://github.com/infinri/WritRetrievalSystem/actions/runs/43540148638),
registered while its quality job was still running. The prior local workspace
outage and restored checkpoint are documented separately; faster runs were not
selected retrospectively. Exact models, input hashes, code revisions, archive
hashes, environment and all commands accompany the results. The new host used
Python 3.12.16, four virtual CPUs on AMD EPYC 7763, Temurin 21.0.13+9, Relate 1.0.1,
Neo4j Community 5.26.0, fixed MiniLM ONNX/tokenizer and Rust 1.85.1. This differs
from the original local Python 3.12.14 / Intel host and is a new replication.

There are 64 formulations / 32 topic families, split into 32 development and
32 held-out tasks (16 families each). Held-out positives: 20 tasks / ten families,
24 target instances, only five distinct source versions. Unknown controls:
12 tasks / six families. Labels are **model-authored, NOT HUMAN REVIEWED**.
The 120-character labels are answer-bearing proxies; matching all proxies with
exact source versions/digests is not independent proof of full answer sufficiency.
Wider qualifications must be reviewed. A URI hit or a truncated-away proxy never
counts. Historical tasks exclude future answer-bearing documents.

| Matched arm | Complete labeled targets /20 | Delivered proxies /24 | MRR | Empty abstentions /12 | Full query E2E p95 ms |
|---|---:|---:|---:|---:|---:|
| A flat lexical | 13 | 15 | .410 | 4 | 30.4 |
| A flat vector | 8 | 9 | .232 | 4 | 30.8 |
| A flat hybrid | 14 | 17 | .300 | 4 | 30.6 |
| B native Relate candidates / app fusion | 13 | 15 | .292 | 4 | 39.7 |
| C native Relate fusion | 13 | 15 | .292 | 4 | 38.4 |
| D native Neo4j fusion | 12 | 14 | .285 | 4 | 72.5 |
| Connected A/B/C/D | 8 each | 9 each | .221 | 4 each | 36.3 / 42.4 / 39.2 / 74.6 |

These quality timings include permitted-set resolution, generation validation,
inference, retrieval, validation and complete rendering; each p95 uses 96 timings
from 32 prompts × three repetitions, not 96 independent tasks. No p99 is claimed
for these small quality runs. No positive task unnecessarily produced empty
context. Returned citation/scope checks passed. Empty context is a retrieval
abstention metric, not a live agent's judgment.

The best-configured track uses only the pre-held-out development selection.
A/B/D connected reach 9/20 while C stays 8/20; flat outcomes are unchanged.
Against A-hybrid, one-sided paired-family 95% lower bounds for complete-target
delivery are -.15 for B/C-flat and -.20 for D-flat (registered margin -.03).
Neither meets noninferiority. Unconditional expansion crowds out targets under
the common payload budget. Lexical has higher MRR than hybrid but less complete
coverage, so no single semantic quality winner is established by this proxy set.

All per-task regressions, unchanged results, full payloads, exact refs, rankings,
omissions and errors remain in the raw data. [Detailed tables and summaries](evidence/recovered-ci/43540148638/FINDINGS.md),
[quality/ANN curves](evidence/recovered-ci/43540148638/comparison.svg), and
[machine-readable results](evidence/recovered-ci/43540148638/summary.json) preserve
all denominators. Labels are not an independent human or causal outcome review.

## Load, resources and responsibility split

All 24 registered profiles ran: **18 completed; six failed their limits**.
Completed profiles have 1,000 samples after ten warmups; failed profiles retain
available partial samples and receive no adoption percentiles. One/four active
readers, 188 / 1,880 / 18,800 units, randomized order, fixed limits and resource
sampling are recorded. 10x/100x are synthetic load, not real-data quality evidence.

| Static prepared-generation example | E2E p95 ms | Peak total observed RSS MiB | Result |
|---|---:|---:|---|
| A, 1x, one reader | 25.8 | 408.9 | complete |
| B, 1x, one reader | 34.6 | 484.4 | complete |
| C, 1x, one reader | 34.7 | 483.7 | complete |
| D, 1x, one reader | 55.2 | 1187.1 | complete |
| A, 10x, one reader | 107.6 | 441.7 | complete |
| D, 10x, one reader | 61.8 | 1222.6 | complete |
| D, 100x, one/four readers | 107.1 / 283.5 | 1904.2 / 1899.8 | both complete |
| A/B/C, 100x, one reader | — | recorded in raw data | query timeout |
| A, 100x, four readers | — | recorded in raw data | query timeout |
| B/C, 100x, four readers | — | about 4832 each | cooperative RSS failure |

The server profile shows useful load behavior at larger scale, but its lower
held-out target delivery and higher resource cost prevent an adoption claim.
At small scale, A is faster and smaller. No native configuration establishes the
registered equal-quality 1.20x E2E improvement / <=1.10x RSS adoption result.
No remote server results, energy costs or minimal deployment footprint are inferred.

Important limits: four-reader native profiles retain an extra idle warmup reader;
process-per-reader Relate duplicates storage/runtime state. These costs belong
to the tested prototype, not an inherent limit of Relate. The 2 GiB RSS budget
is cooperative, checked after setup/during queries, not an OS limit during import.
Observed RSS is app + model + DB/worker descendants sampled every 20 ms; peaks
may be missed. CPU is SELF + waited CHILDREN and can omit unwaited descendants.
Working disk excludes shared model/runtime/distribution footprints; recorded
shared sizes are separate and full Java/interpreter deployment disk is unmeasured.
Static warm profiles exclude canonical live refresh and are distinct from the
quality timing path. Empirical p99 has about ten tail samples per complete
profile; block-bootstrap intervals describe this one run, not cross-host certainty.

## Stronger flat ANN load control

A separately [registered, exploratory ANN diagnostic](evidence/ann-diagnostic/README.md)
checks whether exact-vector A was an unfair large-scale control. At 18,800
synthetic units on a new common local host, single-reader HNSW flat p95 is
127.5 ms, versus exact flat 164.2 ms and native Neo4j 75.1 ms. Four-reader ANN
hits the 180-second query limit; all other five cells complete 1,000 samples.
Four cached development vectors have strict exact-oracle recall .90/1/.90/1 and
tie-aware recall 1 each. No held-out semantic queries were rescored or tuned.
The full permitted-hit keyword materialization is still a substantial flat-control
cost. These measurements are separate from the primary hosted timings and do
not establish equal-answer-quality or a universal native/flat winner. The primary
quality and correctness adoption barriers remain.

## Native mechanics and language

Actual engine checks establish native vector/fulltext queries, Cypher RRF,
permitted partitions, supplied required bundles, stored citation validation,
explicit manifest/index corruption failures, cycles/irrelevant-edge exclusion,
and actual Neo4j process restart. **19 cross-engine projection gates pass**;
ten native Relate pytest cases include actual rollback and failed replacement
publication while the prior generation remains recoverable.

Global native top-k followed by project filtering loses permitted hits in the
registered starvation test. Allowed-only partitions prevent that failure and
hidden-IDF influence, at an import/duplication/update cost. This is application
policy, not built-in database authorization. Relate's reported HNSW metadata is
compatibility metadata: the pinned source enumerates/scans index population;
raw oracle results and source inspection are retained in the recovered local
checkpoint. Standard-no-stop-words metadata does not establish equivalent
analyzer scoring between implementations.

Raw exact-oracle recall is separate from relevance. At k=20 on 188 units:
Relate exact 1.000, Neo4j ANN .9734, HNSW ef100 1.000. At k=50, strict identity
recall for Relate is .999375 with tie-aware recall 1.000; this numerical/tie
boundary difference is retained. Native strict selection overrequests the whole
permitted partition for tie handling; raw ANN curves are a distinct cost profile.

Paired thin-client query probes (200 pairs/backend, ten warmup pairs, randomized
order) return equivalent selections. Python/Rust p95: Relate **9.59 / 9.27 ms**;
Neo4j **17.33 / 14.62 ms**. Rust lowers observed query-client cost here, but
Python outer validation remains, inference/rendering is excluded, bindings and
HTTP clients differ, and no complete Rust context pipeline is measured. This
microbenchmark does not justify a wholesale rewrite or a full-system speed claim.

## Learned reranking, preservation and remaining gates

Independent pinned local Apache-2.0 cross-encoder ablation: 128 calls, twenty
candidates, 384 pair tokens, batch eight, two/one ORT threads, no tuned threshold.
A stays 14/20 while MRR rises .300 -> .581; B/C rise 13 -> 14/20, D 12 -> 13/20.
One conflict task regresses while another improves: unchanged totals do not mean
unchanged outputs. Added processing median **827.8 ms**, p95 **956.9 ms**;
worker peak **461,136 KiB**. Composed E2E is not a directly measured whole-system
reranking latency or combined peak memory. Abstention remains weak. No successful
agent outcomes or causal rule effects follow.

**The primary hosted run passes 127 pytest checks, five original demo checks and
nine scripted restart/retraction checks. Final local validation passes 129 pytest
checks**, adding real HNSW control mechanics and a fake-transport trace-integrity
test (which is not generative-agent evidence). All 79 preservation hashes pass. Original weighted retrieval was
rerun on all 1,012 outputs: this hosted runtime differs on 52 outputs excluding
timing, including Q127 order in lexical/no-graph arms; modes and published
Hit/RR/nDCG metrics are unchanged. Maximum observed score/similarity delta is .0002.
[Exact runtime differences](evidence/recovered-ci/43540148638/historical/runtime-differences.json)
are published, rather than claiming numerical identity across hosts. The restored
same-host local comparison was 1,012 unchanged outputs and remains separately
archived. Neither proves equivalence to the missing original model export.

Actual generative-agent trials are **NOT RUN**: no authorized executable local
model host and exact model identity/revision are configured. The executable
paired fixed-packet tool-calling harness and blind review materials are supplied.
Packet mode logs rewrites without pretending to perform adaptive backend search.
Owner approval stays outside agent tools.

Unsupported adoption gates remain: complete canonical-memory projection/refresh,
trusted shared publication, automatic conflict construction, native confidence/
retraction/replay integration, storage-device faults, complete cold CLI recovery
and remote server operation. Passing retained production tests does not establish
these native integrations. Keep the existing Relate persistence and application
semantics, preserve the baselines, and use a new held-out set before further tuning.
[Removal audit and rollback](REMOVAL-AND-ADOPTION.md): zero production removals.
