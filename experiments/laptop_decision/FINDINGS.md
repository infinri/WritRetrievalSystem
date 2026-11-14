# Laptop architecture validation: findings

Registered protocol: [PROTOCOL.md](PROTOCOL.md), committed before scoring
(`f0bfea8`). Amendment 1 (setup error, before scoring) and Amendment 2 (grader
correction, before regrading) are recorded there. Machine-readable results:
[evidence/decision-summary.json](evidence/decision-summary.json). Labels are
model-authored and **not human-reviewed**. Laptop timings are loopback-only
and are not paired with the hosted or earlier machines.

Four layers are kept separate below: **database correctness**, **retrieval
relevance**, **generated-answer correctness** (model-assisted) and **task
completion** (not measured).

## Source state

Main `0511139` is the PR #9 merge. Its tree is byte-identical to the reviewed
head `f1b8caa` (empty diff). There were no open PRs. The older remote branches
were left untouched. Pinned Neo4j 5.26.0, Relate FFI 1.0.1 and MiniLM
artifacts are byte-identical to hosted run 43540148638. Environment:
[registration/](registration/).

## 1. Database correctness (all pass; integration gaps listed per implementation)

| Check | Result |
|---|---|
| Preserved evidence hashes | 79/79 db_offload, 324/324 reliable_memory unchanged |
| pytest under network denial | 149 passed |
| Original unittest demos | 5/5 |
| Phase 3 restart/retraction checks | 9/9 |
| Canonical-memory workflow demo | PASS, 17 separate processes; generations differ after retraction; active positive contributions 0; rule stays `ai-provisional` |
| Exact source provenance | 254/254 passages (127 distinct texts) byte-equal to Git objects |
| Cross-engine gates (bake-off mechanics) | 19/19 (Relate 9, Neo4j 10); Neo4j process restart 5.3 s |
| Thin clients | Relate and Neo4j, 200 paired probes each, equivalent selections |

Correctness covered by the passing checks above: project/type identity,
exact revision/digest citations, hidden-record and IDF influence with
filtering before candidate limits, foreign-project bridges and bounded
traversal, supersession/expiry/retraction, replay without resurrection,
restored wording under a new revision not rebinding, complete conflict
bundles and hard budgets (maximum payload 6,000 of 6,000 characters), canonical
and index consistency, restart, and failed or corrupt refresh. These are
bounded application and engine checks, not power-loss, adversarial filesystem
or multi-writer guarantees.

**Integration status by implementation** (`integration_status` in the summary):

- **Legacy hybrid** (`reliable.agent context`): supported incumbent. It does
  not implement the explicit source and owner-confirmation request contract.
- **Grounded flat** (`grounded_cli`, backend omitted): supported. No blocking
  gap.
- **Grounded native Relate** (`grounded_cli --backend relate`): supported
  canonical-memory → native-index workflow. Refresh, restart, retraction
  visibility, replay safety, failed build/publication and corrupt-projection
  quarantine are tested on the real engine. Feedback/confidence,
  retraction/replay meaning, conflicts, budget and approval stay in Writ **by
  design**, so their absence from the database is not a gap. Not established:
  concurrency/multi-writer, power-loss and device faults, incremental refresh
  and compaction, large-corpus refresh cost.
- **B/C bake-off Relate prototypes:** static prepared generations. No
  canonical live refresh, no full cold-CLI recovery, no trusted shared
  publication.
- **D bake-off Neo4j prototype:** a static projection on an owned loopback
  server. It is not a canonical-memory backend: live refresh, feedback-ledger
  and recovery integration are missing, and remote operation was not measured.

## 2. Retrieval relevance (opened sets: regression replication, no tuning)

All 288 reliable-memory task × condition repeat-0 outputs (dev and held-out)
are **byte-identical** to the committed evidence. All repetitions are
deterministic.

| Reliable memory | Dev natural /24 | Held-out natural /24 | Held-out all positives /30 | Explicit source /6 | Unknown controls /6 |
|---|---:|---:|---:|---:|---:|
| Legacy hybrid | 17 | 19 | 22 | unsupported (raw 3) | isolation 3/3; owner-confirmation unsupported |
| Grounded flat | 15 | 20 | 26 | 6 | 6 |
| Grounded Relate | 15 | 20 | 26 | 6 | 6 |

Grounded and legacy are mixed: combined natural delivery is 35/48 vs 36/48.
Paired against legacy, grounded improves `dev-02`, `dev-11`, `dev-27`,
`dev-29`, `hel-06`, `hel-28`, `hel-29`, `hel-30` and regresses `dev-04`,
`dev-05`, `dev-07`, `dev-22`. Natural flat − legacy file-cluster bootstrap
95%: dev [−.217, .080], held-out [0, .136], from only five clusters.
Native Relate and flat deliver identical targets on every positive. Candidate
order differs on dev-01/02/03/15/22 and hel-07/08/16/20.

| Bake-off held-out, matched | Complete /20 | Proxies /24 | MRR | One-sided 95% lower bound vs A-hybrid (complete, MRR) |
|---|---:|---:|---:|---|
| A-hybrid flat | 14 | 17 | .300 | reference |
| B / C native Relate | 13 | 15 | .292 | −.150 / −.018, fails −.03 |
| D native Neo4j | 12 | 14 | .285 | −.200 / −.034, fails |
| Connected A–D | 8 | 9 | .221 | −.500 / −.138, fails |

The best-configured track is the same, except A/B/D-connected reach 9/20.
These figures match the hosted run exactly. Citation and scope checks pass,
with zero errors.

## 3. Cost: latency and resources (laptop, Docker, loopback)

**Warm persistent process** (reliable memory held-out, 108 calls per arm,
including inference, validation, retrieval and rendering):

| Arm | p50 ms | p95 ms | Natural p95 ms |
|---|---:|---:|---:|
| Legacy hybrid | 41.2 | 143.7 | 143.6 |
| Grounded flat | 60.3 | 140.8 | 87.0 |
| Grounded Relate | 62.3 | 179.8 | 180.0 |

Whole-run peak RSS is about 703 MiB (all arms plus the model in one process;
not per-arm attribution).

**Fresh CLI process** (60 samples per profile, randomized interleaving, warm
disk, per-process `wait4`):

| Profile | p50 ms | p95 ms | Mean CPU s | Peak RSS MiB |
|---|---:|---:|---:|---:|
| Legacy hybrid | 862 | 1062 | 1.60 | 279.6 |
| Grounded flat | 919 | 1077 | 1.73 | 283.6 |
| Grounded Relate | 1020 | 1294 | 1.80 | **237.7** |

Outputs are deterministic apart from the `snapshot.as_of` request timestamp
(15/15 repeated checks).

**Server load suite** (bake-off corpus; 10 warm-ups, 1,000 samples target;
E2E p95 ms and peak combined RSS MiB including the Neo4j JVM):

| Load | A flat | B Relate | C Relate | D Neo4j |
|---|---|---|---|---|
| 1x, 1 reader | 19.6 / 390 | 29.8 / 438 | 28.0 / 436 | 36.6 / 1170 |
| 1x, 4 readers | 69.4 / 385 | 73.5 / 691 | 76.4 / 688 | 75.0 / 1332 |
| 10x, 1 reader | 74.8 / 438 | 79.1 / 585 | 80.7 / 580 | 52.1 / 1213 |
| 10x, 4 readers | 201.1 / 436 | 115.9 / 1259 | 105.8 / 1253 | 85.8 / 1393 |
| 100x, 1 reader | 222.1 / 587 | timeout | timeout | 73.2 / 1891 |
| 100x, 4 readers | 778.8 / 628 | RSS budget | RSS budget | 100.3 / 1893 |

20 of 24 profiles completed (hosted run: 18). Laptop A-100 completed where
the hosted A-100 timed out. The two runs are on different hardware and are
not paired. Adoption gates (≥1.20x p95, ≤1.10x RSS, quality and integration):
**no profile qualifies**. D is 3.0–7.8x faster at 100x but uses 3.0–3.2x the
memory, fails quality and lacks canonical integration. B/C are 1.7–1.9x faster
at 10x with four readers but use 2.9x the memory and fail quality.

## 4. Generated-answer correctness (fixed-context QA, model-assisted)

QA_RESULTS_PLACEHOLDER

## 5. Task completion

**Not measured.** Fixed-context QA does not run repository edits, tool use
or rule application. No causal benefit of an individual rule is established.

## Limitations

- The labels are model-authored and unreviewed. Exact-passage delivery is a
  proxy. Held-out sets were already opened and are regression data only.
- The QA is a protocol adaptation. Temperature, seed and model artifact
  revision are unavailable through the host. The 512-token output cap was not
  enforced (actual tokens recorded). Built-in Claude Code plugins and
  host-appended guidance could not be removed. Answer grading is
  model-assisted. The empty context reveals condition A, and the packet format
  separates legacy from grounded.
- Laptop: shared interactive machine with frequency scaling and no container
  limits. Loopback only, so no remote-server inference.
- Debian OpenJDK 21.0.13+9 was used in place of Temurin. The four-reader
  native profiles keep an extra idle warm-up reader, as in the prototype.
- Not established: concurrency/multi-writer, power-loss and device faults,
  incremental refresh and compaction, authenticated tenancy.
- Human review of labels and answers is pending. Materials are in
  `evidence/qa-human-review/` and `evidence/bakeoff-report/review/`.
