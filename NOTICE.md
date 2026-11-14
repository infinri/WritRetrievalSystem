# Upstream attribution

Writ Retrieval System reuses Writ V1 code and fixtures by **Lucio Saldivar**, from
[infinri/Writ](https://github.com/infinri/Writ) at
`ebdafe5450b201339f81e717ed104e6bcfd3fe3e`, under the accompanying [MIT license](LICENSE).
The retrieval and decision-memory foundation predates this hackathon entry.

Decision-memory concepts and the recall eviction policy retain Writ's credit to
[JolliAI](https://github.com/jolliai/jolliai) and its ContextCompiler: the policy
was adapted, rather than Jolli's code. Writ added rule grounding.

| Extracted area | Upstream source | Adaptation here |
| --- | --- | --- |
| Hybrid retrieval | `writ/retrieval/{pipeline,keyword,embeddings,ranking,traversal,collectors,node_scope}.py` | Namespace changes, Relate read boundary, independent artifact locations and diagnostics. Ranking weights, candidate filters, abstention, scope predicate, budget projections and tie handling retained. |
| Document retrieval | `writ/retrieval/documents.py` | Same read boundary and shared indexes; only its fenced clamp helpers copied from `injection_ceiling.py`. No host prompt-assembly services. |
| Decision recall | `writ/session/recall.py` | Namespace change and Relate implementation of required record reads. Recall remains separate from rule candidates. |
| Supporting logic | `writ/frequency.py`, `writ/shared/{atomic_file,injection_text,tokens,trust}.py`, `budget.json` | Namespace changes; original computation and formatting retained. |
| Graph contracts | `writ/graph/schema.py`, `predicates.py`, `db/_common.py`, record/node/abstraction store reads | Only necessary registries/predicates and read semantics. No Neo4j driver, server, write services, hooks, or Writ V2 kernel. `normalize_path` alone copied from `session/remote_parse.py`. |
| Corpus and evaluation | `writ-corpus.cypher`, three ground-truth JSON files, `tests/fixtures/retrieval_scoring.py` | Byte-identical fixtures, no added rules or relationships. Corpus resides in `tests/fixtures/`. |
| Regression tests | `test_retrieval_node_scope.py`, `test_retrievable_filter.py`, `test_recall_compile.py`, `test_ranking_tie_determinism.py` | Import namespaces and source-file location updated. Additional integration tests are new. |

[Source hashes](docs/UPSTREAM-MANIFEST.json) identify original files. Historical
measurements in copied comments describe upstream work, not results measured here.
[Validation](docs/VALIDATION.md) states the evidence for this extraction.

New work includes the Relate adapter/importer, standalone CLI and packaging,
artifact setup, integration tests, controlled parity capture and documentation.
OpenAI Codex assisted with implementation and validation. Human review and the
final contest submission are pending.

The optional public ONNX download is `sentence-transformers/all-MiniLM-L6-v2`,
revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` (Apache-2.0). The setup script
retains its model README and writes artifact hashes. Model weights are not
included in this repository; this export is not claimed numerically equivalent
to the original Writ maintainer's local export.

## Phase 2 reuse

Local capture models, record MERGE/provenance and edge semantics adapt
`writ/graph/schema.py`, `graph/db/record_store.py`, `session/decision_capture.py`
and `session/commit_capture.py`. Durable feedback and served absolute-count
refresh adapt `graph/db/rule_store.py`, `session/feedback.py` and the retained
`frequency.py` algorithm. The local proposal/review policy follows
`writ/promotion.py`'s distinction between statistical crossing, human approval
and invalidated observations after wording changes. Existing JolliAI credit for
decision memory/recall remains applicable.

The local manifest interfaces, qualified identity, transactions, permanent replay
receipts, per-claim/outcome deduplication, separate record context and terminal
review boundary are this adaptation's implementation. The original hook/token
authorization service, auto-feedback heuristics and source-export/structural gate
are not imported. See [PHASE2.md](docs/PHASE2.md) for the narrower trust boundary. New experiment
harnesses and synthetic fixtures are project work, not upstream quality claims.

## Phase 3 design and public-history reuse

Selected design principles and redistributable MIT Writ history come from
`v2/architecture-rebuild` at `82971fdbfd0a8650db247e832cf8df89948e2cd6`, including
`retrieval-and-memory.md`, `data-model.md` and D-035/D-036. Frozen exports retain
the upstream license, source revisions and attribution. New Python contracts,
local generations and evaluation tooling implement this adaptation's narrower
scope; no Rust kernel, broker or enterprise infrastructure is ported. Existing
Writ and JolliAI credits above remain applicable.

## Canonical-memory follow-up

The opt-in native projection and grounded-context workflow applies Writ V2
retrieval/memory design inputs at `a0e0e413e3b20082a85e7d75c58b45b0ba09b903`.
New public source passages retain exact MIT Writ citations and the existing
Lucio Saldivar / JolliAI attribution. OpenAI Codex assisted with implementation,
provisional labels and evaluation; independent human review remains pending.
