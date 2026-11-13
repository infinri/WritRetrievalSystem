# Extraction plan

Source: `infinri/Writ`, `main`, commit `ebdafe5450b201339f81e717ed104e6bcfd3fe3e`.

## Scope

Extract Writ V1's connected retrieval behavior into a standalone application using Relate. Preserve measurable baseline behavior before changing ranking or expanding the corpus. Writ V2's kernel, broker, authorization, and development branch are outside this extraction.

## Source map

| Area | Existing Writ source | Work required |
| --- | --- | --- |
| Pipeline | `writ/retrieval/pipeline.py` | Separate shared config/logging/trust imports and graph access; preserve filtering, abstention, scoping, ranking, and rendering semantics. |
| Lexical retrieval | `writ/retrieval/keyword.py` | Retain Tantivy behavior as a comparison baseline; verify index reload/build behavior. |
| Embeddings/vector index | `writ/retrieval/embeddings.py` | Extract ONNX model loading and HNSW persistence with explicit artifact setup and declared dependencies. |
| Ranking | `writ/retrieval/ranking.py` | Preserve existing defaults before evaluating alternatives. |
| Graph traversal | `writ/retrieval/traversal.py` | Replace direct Neo4j-driver access with a tested Relate interface; preserve visibility metadata and bounded expansion. |
| Schema and selection | `writ/graph/schema.py`, `writ/graph/predicates.py`, `writ/retrieval/node_scope.py` | Identify the required subset without weakening mandatory/superseded filtering or project scope. |
| Decision context | `writ/graph/db/record_store.py`, `writ/session/recall.py` | Keep record recall distinct from rule candidates; preserve provenance and attribution. |
| Corpus/evaluation | `writ-corpus.cypher`, `tests/fixtures/ground_truth_queries.json`, `tests/fixtures/ground_truth_proc.json` | Validate import compatibility and relevance of fixture IDs before making quality claims. |

The retrieval folder is not self-contained. For example, `pipeline.py` imports `writ.config`, graph schema/predicates, shared trust/logging helpers, and other retrieval modules. `AdjacencyCache.build_from_db` accesses Neo4j's driver/session directly. A folder copy alone is not a working extraction.

## Milestones

1. **Relate foundation — implemented:** package, CLI, synthetic decision graph, persistent directory, separate-process reopen, and four integration checks.
2. **Baseline extraction — implemented:** standalone source/dependencies, license and attribution carried over; controlled query outputs match the unmodified pinned upstream code. See VALIDATION.md for the exact evidence and limitations.
3. **Relate graph adapter — baseline reads implemented:** full pinned corpus import, candidate/adjacency/category/abstraction reads and record recall run on the actual engine. Production migration and broader compatibility remain pending.
4. **Connectivity audit — implemented for the supported workflow:** qualified identities, typed edge contracts, explicit intentional exclusions, bounded visible record context and audit counts cover ingestion through rendered output. Foreign bridges, cycles, duplicate IDs and unrelated neighbors are tested. Audit-only revisions/receipts can be intentionally isolated; no arbitrary corpus links were added.
5. **Evaluation — implemented with bounded conclusions:** pinned baseline and Phase 2 full-corpus ablations, per-query results, eligibility, abstentions, timings/RSS and paired regressions are in evidence/. Connected history/feedback is evaluated on six synthetic prompts; independent real-project usefulness and causal outcome evidence remain pending. See FINDINGS.md and PHASE2.md.
6. **Submission — pending:** reproducible install, inspectable persistent sample store, concise reuse/tool disclosures, demo recording/edit, and Devpost entry. Keep the public topic `relate-hackathon` set on GitHub.

## Boundaries

Retrieved text and graph facts are context, not authorization. A recorded rule ID is attribution, not evidence that an agent complied. No performance, safety, or quality improvement is claimed by the initial persistence demo.

Preserve upstream credits when the decision-memory code is imported; its Writ documentation attributes parts of the design to JolliAI. Pin model/data artifacts and record licenses before publishing them as submission assets. The private organizer conversation is not a repository asset.

## Phase 3 adaptation

Selected V2 principles are implemented in the separate `reliable` path; see the
[scope map](phase3/V2-SCOPE-MAP.md), [contracts](phase3/CONTRACTS.md) and
[commands](PHASE3.md). Public time-separated source recovery, coherent generations,
explicit evidence retraction and one total payload budget now have measured
results. The [findings](phase3/FINDINGS.md) retain the relevance regression and
abstention failures; no graph superiority, human label review or live-agent task
success is claimed. This does not expand the extraction into Writ V2's broker.
