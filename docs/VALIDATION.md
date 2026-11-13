# Validation

## Current Phase 2 evidence

2026-11-13: **94 pytest tests passed**, including the original 76 and 18 new
workflow/metric checks. The separate unittest demo suite remains **5 passed**;
`pip check` passed. A built wheel was reinstalled into a separate venv and its
connected-context command ran outside the checkout using real ONNX inference.

A full-corpus baseline was committed before behavior changes. Four retrieval
arms × 253 original prompts were rerun after implementation; all 1,012 projected
outputs match after excluding timings. A supported-interface synthetic scenario
ran capture → close/reopen → recall → feedback → subsequent context, with all
provenance, lifecycle, replay, contradiction and project controls passing.

See [FINDINGS.md](FINDINGS.md) for metrics, regressions and limits,
[PHASE2.md](PHASE2.md) for runnable commands, and
[RUN-PROVENANCE.json](../evidence/RUN-PROVENANCE.json) for source-tree mappings.
An initial hosted CI attempt crashed with SIGILL while importing a reused
`hnswlib` wheel. hnswlib 0.8.0 defaults to `-march=native`, which can make a
cached wheel incompatible with another runner CPU. CI now forces an uncached
source build with `HNSWLIB_NO_NATIVE=1`; no test is skipped to hide the crash.
The original export equivalence remains unverified. History/outcome usefulness
is demonstrated only on synthetic inputs; authenticated service/host delivery,
concurrent writers, automatic harvesting and causal outcome evidence remain open.

## Historical extraction record

The following records the state at PR #1, before Phase 2. Its then-open gaps are
historical; qualified record enrichment and durable capture/feedback now exist.

Baseline extraction, 2026-11-13. Source Writ V1 `main` at
`ebdafe5450b201339f81e717ed104e6bcfd3fe3e`; starting repository commit `d9829fd`.

## Executed locally

Python 3.12.14, Linux x86_64. Installed in a fresh virtual environment with
`CC=gcc CXX=g++ python -m pip install -e '.[dev]'`. This runtime's default compiler
name was `clang++`, which was unavailable; explicitly selecting the installed GCC
resolved the hnswlib build. This did not require a code or algorithm change.
Exact resolved dependencies are in `requirements-validated.txt` (Relate 1.0.1,
Tantivy 0.27.0, hnswlib 0.8.0, NumPy 2.5.4, ONNX Runtime 1.32.0).

| Command/check | Observed result |
| --- | --- |
| `python -m pytest -q` | 76 passed; no model download and no Neo4j server. |
| `python -m unittest discover -s tests -v` | 5 passed, including the original four demo checks and separate-process recall. |
| `python -m pip check` | No broken requirements. |
| Built wheel installed into a second clean venv; query run from `/tmp` | Full-corpus ONNX query completed with no `neo4j` package installed; packaged budget JSON and upstream NOTICE present. |
| Full pinned corpus import, close/reopen and collectors | 468 nodes, 1,268 edges; 288 Rule nodes; 317 ranked units (256 Rules, 16 Skills, 15 Playbooks, 14 Techniques, 14 AntiPatterns, 2 ForbiddenResponses). |
| `init-demo`, `context src/payments.py`, `recall src/payments.py --project writ-demo --project-root . --full` | Original context chain and separate recall both returned DEC-001 / PARAM-001. |
| `prepare_model.py` and `query 'controller contains SQL query' --model-dir data/model --project example` | Real ONNX/Tantivy/HNSW/Relate query completed, `mode=standard`, 54 candidates, top ID `DB-SQL-002`. A smoke execution, not a quality benchmark. |

The suite includes upstream scope, routing, budget/eviction and cross-process tie
regressions. New real-engine checks cover candidate collection, mandatory and
superseded exclusions, auxiliary methodology text, source provenance properties,
edge direction and category exclusion, abstraction members, persisted index
reload without bulk re-encoding, exact project recall (including duplicate IDs
and a hostile cross-project edge), path limits/deduplication, document scope,
and abstention after exclusions. A separate controlled adjacency fixture verifies
record visibility in enrichment/proximity.

## Controlled upstream parity

`python scripts/capture_v1_reference.py --upstream /path/to/pinned/Writ` ran the
**unmodified upstream query/index code** at the exact commit. The script checks
the checkout commit and clean tracked state and hashes four original modules.
Import-time database registries are shimmed; no upstream Neo4j reads run.
Inputs are the same independently checked Relate snapshot, and both sides build
actual Tantivy and HNSW indexes with a deterministic synthetic 384-dimensional
encoder. Seven query cases cover semantic/literal selection, node-type selection,
exclusion, abstention and small budgets.

`tests/fixtures/v1-controlled-results.json` is the captured upstream reference.
The integration test compares full output (order, scores, mode, relationships,
render projections and abstention signal), excluding only elapsed time. It
matches. This proves parity on these controlled inputs, not all possible inputs
or end-to-end Neo4j/Relate numerical parity with the original model export.

## Corpus and fixture eligibility

The copied corpus has SHA-256
`cc34b71a9c7c1eddc06b8ba296b78a3b2c3fec151847eee088399095134d9e96`.
The import preserves its IDs, properties, edges, labels and directions using its
original statements; it does not add connectivity. The importer refuses an
existing destination or a different dump. Import staging avoids publishing a
partially completed graph on failure.

Copied unchanged: 193 coding-rule gold queries, 40 methodology queries, 20
negative queries, and upstream scoring helpers. The eligibility audit found no
missing primary target IDs. **21 of the 193 coding queries target rules excluded
from the ranked pool at this baseline** (mandatory/superseded policy); all 40
methodology primary targets exist in the ranked pool. Ranked-pool membership is
not the same as semantic-route eligibility. The exact query IDs are recorded in
[FIXTURE-ELIGIBILITY.json](FIXTURE-ELIGIBILITY.json). Gold fixtures are preserved,
not relabeled or weakened to inflate scores.

## Model artifact

Public `sentence-transformers/all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, Apache-2.0:

- `onnx/model.onnx`: `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452`
- `tokenizer.json`: `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037`

The setup script verifies these bytes and records the retained model README too.
The model family, pooling, normalization and 128-token truncation are retained.
The original maintainer's local optimum export is not supplied or pinned by V1;
this public export's numerical equivalence to it is **unmeasured**. The CLI keys
cache directories by artifact bytes; library callers must isolate encoder caches.

## Remaining gaps and boundaries

- No retrieval-quality comparison, ablation, full gold-set scoring, performance
  benchmark, memory measurement or improvement claim in this milestone.
- No live Neo4j comparison. The corpus is a pinned snapshot; production record
  migration, incremental ingestion and authenticated service deployment are outside
  this extraction. Decision recall is tested with synthetic records.
- V1 adjacency identifies nodes with its doctrine-ID coalesce. Record-only IDs
  (`decision_id`, `change_id`, `commit_hash`, etc.) are not in that projection,
  so most record edges do not enter the rule adjacency cache. This inherited
  connectivity gap is deliberately retained for baseline parity. Separate decision
  recall uses explicit record fields and does retrieve those paths. Adding record
  bridges could change ranking and requires a later measured change.
- V1 indexes/cache maps are keyed by a single unit ID, not `(project, ID)`.
  Record recall handles same IDs in different projects; duplicate doctrine IDs or
  document chunk IDs across projects remain an unsupported index ambiguity. Corpus
  IDs and tested document chunk IDs are unique.
- Partial category routing retains V1's whole-pipeline legacy fallback. The
  connectivity audit must distinguish intentional exclusions from missing edges.
- Standard diagnostics replace Writ's host-specific durable audit router. This
  application provides context, not agent enforcement, permissions or an audit
  compliance service.
- Judge-machine install, Windows support, organizer/submission checks and human
  review remain pending. Copied historical benchmark comments are not local results.
