# Reuse, models and tools

Writ MIT code/data and Lucio Saldivar / JolliAI credits remain in root NOTICE.md.
This experiment reuses the original Tantivy wrapper, pinned ONNX encoder, local
contracts/fixtures and public Writ V2 documents at the recorded source revisions.
Retrieved source text is not authenticated approval or a broker permit.

Relate 1.0.1 Python wheel and official C ABI 2 release: Apache-2.0. The thin Rust
client declares documented ABI signatures; the native binary/header are external
pinned inputs, not relicensed or bundled here. Neo4j Community 5.26.0 is an external
GPL Community runtime, not bundled into this MIT repository. Rust serde_json and
transitives are locked in Cargo.lock; preserve their MIT/Apache notices.

MiniLM embeddings use the inherited pinned Apache-2.0 public export. The optional
cross-encoder uses its separate pinned Apache-2.0 model card/artifacts and is a
learned reranker, unlike embedding similarity/RRF. Weights are not committed.
OpenAI Codex assisted implementation, provisional task/label authorship and
analysis. No independent human label review or generative-agent outcome evidence
is implied by that assistance or automated tests.
