# Responsibility ownership: Relate vs Rust

Pinned engine: `relate` 1.0.1 from crates.io (source tag v1.0.1, commit `ef436ce`), with
Rust 1.88.0 (the engine's declared `rust-version`). Every capability marked "Relate"
below is exercised against the real engine in `tests/engine_capabilities.rs` and
`tests/workflow.rs`. None is mocked.

"Database guarantee" means the engine provides it. "Our semantics via queries" means
Relate executes it, but the meaning (scope, lifecycle, retraction) is our rule expressed in
Cypher. Relate does not know our evidence policy.

| Responsibility | Owner | Kind | Where |
|---|---|---|---|
| Canonical records, relationships, receipts | **Relate** | database guarantee (persistence, WAL, Parquet checkpoints) | `memory.rs` writes |
| Atomic multi-record writes, rollback | **Relate** | database guarantee (transactions) | `Store::tx` |
| Single writer; read-only opens beside it | **Relate** | database guarantee (writer lease) | `Store::open` |
| Full-text index and search | **Relate** | database guarantee (`CREATE FULLTEXT INDEX`, `db.index.fulltext.queryNodes`) | `context::search` |
| Vector index and search, scope filtered before the limit | **Relate** | database guarantee (`SEARCH … VECTOR INDEX … WHERE … LIMIT`) | `context::search` |
| Scope and lifecycle filtering inside search | **Relate executes; our rule** | our semantics via index membership (`search_scope`, `FT_<scope>` labels) | `memory::set_searchable` |
| Expiry (`valid_to`) and as-of time | **Relate executes; our rule** | `WHERE` in the same statement, before the limit | `context::search` |
| Reciprocal Rank Fusion | **Relate** (default) | one Cypher statement (`CALL { … UNION ALL … } … sum(1.0/($rrf+rank))`) | `Fusion::Cypher` |
| Typed, bounded traversal with visibility | **Relate executes; our rule** | Cypher patterns with `project IN $scopes`, `SUPERSEDES*1..4`, one-hop typed links | `context` enrichment |
| Parameterization | Rust | all statements use `$params`; labels and index names are hashes, never user text | `db.rs`, `util::scope_tag` |
| Source extraction (Markdown paragraphs at an exact Git revision) | Rust | reads Git objects via `git cat-file`; no checkout or hooks | `extract.rs` |
| Embedding inference | Rust | pinned MiniLM ONNX through tract (pure Rust), HF tokenizers | `embed.rs` |
| Request contracts (explicit source, owner confirmation, history) | Rust | `writ-context-request/1`-compatible | `context.rs` |
| Exact identity, revision and digest validation | Rust | bindings checked on write; digests rechecked at render and in `verify` | `memory.rs`, `context.rs` |
| Evidence interpretation (active, retracted, expired, revision-bound) | Rust | the engine stores association state; we interpret it | `context.rs` |
| Replay safety | Rust policy, Relate storage | receipts keyed by request id and canonical digest, written in the same transaction | `memory::receipt` |
| Verification, approval, confidence | Rust (by refusal) | imports and captures cannot set them; no approval command exists | `memory.rs` |
| "Why" explanations, budget, rendering | Rust | complete records only, indivisible conflict bundles, hard UTF-8 byte and codepoint limits | `context.rs` |
| Agent interface | Rust | read-only MCP (two tools); IPv4/IPv6 denied by seccomp | `mcp.rs`, `offline.rs` |
| Recovery | Relate (WAL replay); Rust fails closed | a corrupt store refuses to open; `verify` detects tampered rows | tests |

## Where native capability was insufficient, and the smallest alternative

| Need | Native gap in 1.0.1 | What we did (smallest change) | What we did not build |
|---|---|---|---|
| Lexical search filtered to the caller's scope, before the limit | `SEARCH … FULLTEXT INDEX … WHERE` is a syntax error. A global `queryNodes` then filter lets hidden documents affect IDF. | One native full-text index per caller scope, over a label that our writes keep equal to that scope's active records (own plus `_shared`). Measured: hidden documents change shared-index scores but not the per-scope index. | No Tantivy, no custom inverted index |
| Lifecycle filtering inside vector search | Vector `WHERE` filters the declared property `search_scope`. | Inactive records get `search_scope = 'inactive:<project>'`, so supersession and retraction filter before the limit. | No HNSW, no in-memory vector cache |
| Cosine gate on raw cosine | The engine reports `(cos + 1) / 2`. | `2 * score - 1` in the same statement. | — |
| Exact ranking over the permitted partition | — | Per-list `LIMIT` is the partition size, as in the reference policy; RRF and the final top-k run in Cypher. | No custom ranking module |
| Evidence meaning (support vs retraction, revision binding) | The engine has no such concept. | Relationship properties plus Rust interpretation. | — |

No duplicate cache of records or vectors exists. Relate is the only store, and the
derived indexes are native indexes in the same database.

## Cost of these choices (measured; see RESULTS.md)

- Per-scope full-text labels: creating a new scope relabels `_shared` records and issues one
  `CREATE FULLTEXT INDEX`. This is cheap for the demo (one scope). Scaling to many scopes
  is not measured.
- Exact vector scan of the permitted partition: fine at 127–254 records (warm p50 57 ms
  end to end, including inference). Larger corpora are not measured.
- Fusion owner: Cypher RRF and Rust RRF deliver identical passages on 72/72 regression
  tasks. Cypher is about 1–1.6 ms slower at p50 here (58.6 vs 57.0–57.5 ms). We keep Cypher as the
  default because it moves fusion into the database with no measured quality cost; this is
  an ownership choice, not a speed win.
