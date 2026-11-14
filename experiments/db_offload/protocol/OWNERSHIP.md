# Responsibility ownership and removability matrix

Tested engine pins: Relate Python/native 1.0.1 (tag v1.0.1, `ef436ce`), Neo4j
Community 5.26.0 / Python client 5.28.2 / OpenJDK 21.0.13. Spike statements,
outputs and errors are in `../evidence/capability-spike.json`; later prototype
gates qualify this preliminary map. Relate current main 1.0.2 documentation was
NOT assumed to describe the installed wheel. Neo4j is GPL Community server;
Relate Apache-2.0; Writ MIT attribution is retained.

| Responsibility | Current owner | Verified native API / limitation | Proposed experiment owner | Application semantics retained | Potential removal; compatibility gate |
| --- | --- | --- | --- | --- | --- |
| Generate embeddings | MiniLM ONNX/tokenizers | Neither engine generated these pinned vectors | App/model in all arms | Artifact hash, 384 dims, 128 tokens, text identity | None; different DB must receive identical vectors |
| Store/index vectors | NumPy/HNSW files | Relate CREATE VECTOR INDEX exact scan; Neo4j CREATE VECTOR INDEX HNSW | B/C Relate, D Neo4j | Immutable generation, normalization | HNSW sidecars for a proven profile only; recall oracle, restart |
| Vector search | HNSW or exact NumPy | SEARCH with declared property prefilter in Relate; Neo4j queryNodes returns global ANN top-k | B/C/D | Rebound score conversion, scope before cap, ANN recall | Candidate HNSW/exact scan code; hidden-neighbor starvation gate |
| Keyword index/search | Tantivy | FULLTEXT + queryNodes in both; Relate fulltext WHERE rejected | B/C/D with permitted-set partitions | Query normalization, analyzer differences and hidden-IDF isolation | Tantivy dependency only after quality/IDF gates, not globally yet |
| Hybrid fusion/order | App weighted score or RRF | CALL subquery + UNION ALL + sum works in both | B app; C/D Cypher RRF | Candidate bounds, RRF policy, identity ties | New profile's app fusion only; compare every fused ID/score |
| Typed expansion | GraphSnapshot/Python BFS | MATCH variable-length + all(nodes(path)) works in both | B app; C/D query | Allowed relationship types, binding checks, 2 hops/64 bounds | BFS execution only if exact path/scope gates pass; validation stays |
| Scope/type/time/lifecycle | node_scope, reliable contracts | WHERE works; native index scope differs; no DB inferable caller authority | Projection + C/D query | Trusted local project resolution, explicit shared publication, as-of cutoff, tombstones | No blanket removal; pre-cap and invisible-bridge tests |
| Decisions/memories/evidence/history | Relate + LocalStore/ReliableStore | Both persist nodes/edges and transactions; Cypher does not define their meaning | Keep durable contract APIs | Unknown rationale/outcome, captured exact versions, owner boundary | No removal proved by a candidate-search benchmark |
| Active confidence | Python active_counts/frequency | Aggregation possible; not a native Writ policy | App initially | >=50, >=.75, exact bound outcomes, confirmed evidence | Not removed without policy/retraction equivalence |
| Retraction/supersession/replay | ReliableStore receipts/revisions | DB transactions store operations; no built-in replay meaning | App semantics + DB persistence | Never resurrect or rebind restored wording; uncertain commit handling | Keep store/receipts, test actual engines and bridge refresh |
| Snapshot/index freshness | Immutable files + CURRENT | DB read transactions/index visibility, not cross-engine publication | App generation publish + native indexes | Build before publish, old generation, use-time revision/digest checks | External text/vector files possibly; publication manifest stays |
| Citations/exact lookup | Typed Key/digests/source refs | MATCH on qualified identity, properties | DB lookup + app verifier | Source version and delivered clause, not just URI hit | Keep canonicalization/verification; duplicate ID and corruption gates |
| Abstention/conflicts | App rendering/selection | DB can supply scores/claims, cannot decide warranted unknown | App | Both conflict sides or explicit required error, no permission | Keep; compare unknown/necessary abstention |
| Total budget | reliable/budget | No native model-payload contract | App | Full UTF-8/codepoint accounting including citations/metadata | Keep; full required passages cannot be silently clipped |

`WHERE`/Cypher fusion are OUR QUERY BEHAVIOR, not additional built-in security
or replay guarantees. Materializing a permitted-only index partition is application
work and costs memory, import time and updates. A global top-k followed by a
filter is demonstrated non-equivalent. No modules/dependencies are removed now;
the final decision distinguishes reachable removal from untested proposals.
