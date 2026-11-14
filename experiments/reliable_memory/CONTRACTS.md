# Opt-in reliable-memory contracts

This implements selected retrieval/memory parts of Writ V2 at `a0e0e413e3b20082a85e7d75c58b45b0ba09b903`. The Phase 3 contracts remain the canonical ledger contracts. No kernel, broker, authentication service or execution permission is added.

| Responsibility | Existing guarantee retained | New opt-in behavior |
| --- | --- | --- |
| Canonical capture / feedback | ReliableStore transaction/revision, exact Rule/Decision/Outcome bindings, durable receipts, separate owner confirmation | All native search rows derive from one exported transaction; native indexes never own these semantics |
| Source identity | Qualified Key, immutable source revision and text/subject digests; source statements unverified | Bounded read-only Markdown paragraph ingestion; optional complete comparison against local Git objects |
| Index freshness | Content-addressed source snapshot, complete replacement, failed refresh unavailable | Separate native persistent Relate index per permitted/request-filtered partition; complete database-file manifest, exact text/vector/payload bindings, read-only reopen |
| Publication | Source generation remains inspectable | `writ-grounded-pointer/1` publishes source generation + revision + projection identity/manifest together, with previous distinct source generation |
| Lifecycle | Retraction and supersession preserve historical ledger records | Current records only by default; stale-subject Evidence excluded. Explicit history can include clearly marked historical/retracted/obsolete evidence |
| Graph | Typed, source-bound relations, two hops / 64 visits; invisible/retracted bridges excluded; non-seed Rules excluded | Ranked candidates precede optional enrichment. Required/mandatory/conflict bundles still take priority. Old unbound extra edges remain intentionally excluded |
| Evidence request | Integrity, source verification and approval remain separate | `writ-context-request/1` supports a source URI+revision OR current exact record binding, optional owner-confirmed evidence, explicit history flag |
| Output | One complete UTF-8 / character budget; explicit required-content errors | Full joined record text; no 640-character truncation; rendered-text digest; deterministic indivisible conflict bundles and omission metadata |
| Approval | Actual local terminal judgment, distinct from correlated observations | No approval/confirmation command in the grounded agent CLI; no imported text can grant verification |

## Context requests

```json
{"contract_version":"writ-context-request/1","source":{"uri":"https://github.com/infinri/Writ/blob/EXACT40HEX/docs/architecture/retrieval-and-memory.md#L5","revision":"EXACT40HEX"},"verification":"owner_confirmed","include_history":false}
```

Replace placeholders with real values. `source` accepts only URI and revision selectors (Source's other optional fields are rejected). Alternatively supply `binding` as the exact `{ref, revision, content_digest}` returned by inspection. A binding must match the node in this snapshot, including its current lifecycle revision. An old pre-supersession binding cannot silently rebind to a later record. Use a historical source selector or inspect the exact old snapshot for historical material.

`evidence_assessment.status` is `requirements_satisfied`, `insufficient` or `unassessed`. The first means that at least one permitted **complete** record meets the explicit mechanical request and is delivered. It says nothing about general semantic sufficiency or truth. A generic question without requirements is unassessed even when records are retrieved. Owner-confirmed requirements do not treat Git object identity, a content hash, repository text, a tool assertion, or review eligibility as human confirmation. An unavailable/unfittable required record is an error. An absent requested source or verification class yields `insufficient`; mandatory guidance may still be delivered. `abstained` describes empty delivered context; `ranked_abstained` describes candidate selection. Neither is a generated-agent outcome.

## Generations, indexes and recovery

`GroundedSession` reuses the source snapshot/cache implementation with a separate frozen `writ-grounded-policy/1`; the default `ReliableSession` policy bytes remain unchanged. Generation identity covers the full canonical export, revision, encoder identity, policy and lifecycle classification. Counts are recomputed from that export using the retained active-confidence algorithm. Wording restoration under a new revision does not reactivate old observations.

Relate 1.0.1 native `CREATE VECTOR INDEX`, `CREATE FULLTEXT INDEX`, `db.index.vector.queryNodes` and `db.index.fulltext.queryNodes` are tested on actual persistent stores. Vector search scans the whole bounded permitted partition before deterministic ties; `(native_score*2)-1` is compared with the raw cosine gate. Exact-vector mechanics are checked against an application dot-product oracle. Fulltext analyzers are not assumed numerically equivalent: candidate-order differences are published. RRF, typed graph traversal, conflict closure and output assembly remain application-owned.

The native directory contains a read-only Relate database and manifest binding the complete database files, rows, source generation, project and engine profile. Build into a temporary sibling, close/checkpoint the engine, fsync completed files and rename before opening read-only. Validate index text, vectors and citation payload against the canonical rows. Every query also checks file digests, so an open reader cannot conceal offline corruption. Partition before top-k prevents hidden-project candidate starvation and hidden-document IDF influence. Local permitted partitions are application logic, not database authorization. Historical doctrine visibility, including global doctrine types and explicitly supported `_shared` records, is unchanged; caller project selection is a local-owner convention, not authenticated tenancy.

Only after search, contract checks, complete rendering, canonical revision and expiry checks succeed does `GROUNDED-CURRENT.json` publish the source/projection receipt. A failed build, query, render or publication returns no fresh payload. Prior generations are retained for inspection, never served as current after an update failure. `CURRENT.json` remains the legacy pointer. Concurrent threads/writers, protected clocks, hostile same-account modification and power-loss durability have not been established. Process restart is tested.

A corrupt derived index is not silently healed or used. Close the reader, run the owner-only `projection-quarantine` command with its exact identity, then start a fresh context process. Damaged bytes and a recovery receipt are retained; the next context rebuilds and validates from canonical data before publication. No source record or observation is deleted. Quarantine is derived-cache recovery, not evidence retraction.

Caches retain old source/index generations on disk; compaction is not implemented. In-memory native/keyword partition handles are bounded to two per session. A canonical revision currently causes a complete source generation build/embedding pass even if text is unchanged; incremental vector reuse and large-corpus refresh costs remain work.

## Budget and source semantics

The default limits are 8,000 UTF-8 bytes and 6,000 Unicode codepoints for the **entire canonical JSON payload**, including trust, request, snapshot, projection, citations and omissions. Records/conflict bundles are indivisible: skip a whole optional bundle or return `BudgetError` for required content. All delivered text is complete; omitted records are listed in diagnostics. `ceil(chars/4)` remains a heuristic. The pinned MiniLM tokenizer is an embedding tokenizer with 128-token inputs, not a target generative-model tokenizer; no exact output-token claim is made.

The paragraph importer reads Git objects without checkout, hooks, fetch or repository execution. It accepts normalized `.md` paths, at most 32 files / 8 MB / 1,000 selected paragraphs, exact forty-hex revisions, and preserves line/character intervals and source digests in the import receipt. It selects paragraphs 70–1,600 characters long under level-two headings; code/table blocks and other material are not an exhaustive repository export. Identity includes exact Git revision and a path/offset/text digest. Reimport is idempotent, changed immutable meaning is rejected and batch failures roll back. Different snapshots can coexist; importing a newer paragraph export does **not** infer supersession of older paragraphs or identify renamed sections. Explicit lifecycle operations or separate as-of stores are required. Verification against a local object database establishes byte/object identity only; it does not authenticate remote publication or verify assertions in prose.
