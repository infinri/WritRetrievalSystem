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
2. **Baseline extraction — pending:** import the relevant source/dependencies with existing license and attribution; reproduce candidate selection and ranking on controlled inputs.
3. **Relate graph adapter — pending:** test corpus import, node IDs, relationship types/directions, query compatibility, and project scope using the actual engine.
4. **Connectivity audit — pending:** find orphaned nodes, invalid edges, unreachable evidence, stale claims, and relationships lost between traversal and rendered context. A disconnected node is not automatically a defect; record intended semantics before adding edges.
5. **Evaluation — pending:** compare lexical/vector baseline with graph-enabled retrieval on identical queries and corpus; report hit rate, MRR, irrelevant context, latency, memory, and failures. Use synthetic smoke data only for correctness, never as proof of general retrieval quality.
6. **Submission — pending:** reproducible install, inspectable persistent sample store, concise reuse/tool disclosures, demo recording/edit, and Devpost entry. Keep the public topic `relate-hackathon` set on GitHub.

## Boundaries

Retrieved text and graph facts are context, not authorization. A recorded rule ID is attribution, not evidence that an agent complied. No performance, safety, or quality improvement is claimed by the initial persistence demo.

Preserve upstream credits when the decision-memory code is imported; its Writ documentation attributes parts of the design to JolliAI. Pin model/data artifacts and record licenses before publishing them as submission assets. The private organizer conversation is not a repository asset.
