# Database and client-language milestone

D runs Neo4j Community 5.26.0, Java 21.0.13, loopback HTTP JSON. Heap max 512 MiB,
page cache 128 MiB, direct memory max 256 MiB, two JVM processors. The installed
Neo4j Python driver 5.28.2 is not the timed transport. Rust 1.85.1 uses the same
JSON requests and Cypher through a narrow stdio worker; Relate uses official
v1.0.1 C ABI 2, while Python uses its PyO3 binding. This binding difference remains
a confound; these are client-stack comparisons, not proof about languages alone.

Development-final contains all 640 outputs: 32 tasks × 10 arms × two registered
configurations, with three deterministic repetitions each. Twenty tasks have
positive labels and twelve warrant unknowns. Labels remain unreviewed. No error
is dropped from denominators. D-flat delivered all required answer clauses for
18/20, versus 17/20 A-hybrid/B-flat/C-flat; connected versions delivered 15/20.
Four of twelve unknown controls abstained in hybrid arms. These are development
observations, not held-out wins or evidence of successful agent outcomes.

`protocol/selection.json` freezes the choices from development-final before any
held-out run, following the registered answer/abstention/p95 rule. The execution
thread limit is fixed at two model inference threads and one inter-op thread.
Strict native retrieval scans the whole permitted vector partition before
ordering ties; raw ANN curves are a separate experiment. Permitted partitions
and their duplication costs are application policy, not built-in authorization.

The initial equivalent-query language probes used connected mode (200 warm
samples each): Relate Python p95 31.88 ms / Rust 42.95 ms; Neo4j Python 47.18 ms /
Rust 46.09 ms. They exclude inference, validation/rendering outside the worker
and server startup. The small Neo4j difference is not a demonstrated improvement.
No unsuccessful connected architecture is being proposed for adoption: the
wrappers are reusable query clients for subsequent flat probes as well.

The implementation is an immutable candidate-index experiment. It does not
replace canonical memory, evidence/replay, owner approval or snapshot publication
in the production path. Full live-memory projection, trusted shared publication,
and remote-server operation remain integration gates, not passed capabilities.
Existing offline agent controls and all production modules remain intact.

Reproduce (from repository root, optional tools are external to core dependencies):

```sh
CARGO_HOME=/tmp/writ-bakeoff-tools/cargo RUSTUP_HOME=/tmp/writ-bakeoff-tools/rustup RELATE_FFI_DIR=/tmp/writ-bakeoff-tools /tmp/writ-bakeoff-tools/cargo/bin/cargo build --release --manifest-path experiments/db_offload/rust/Cargo.toml
python -m experiments.db_offload.languages --backend relate --rust experiments/db_offload/rust/target/release/writ-db-thin-client --ffi /tmp/writ-bakeoff-tools --model-dir data/model --work data/language-flat-relate --output experiments/db_offload/evidence/language-flat-relate.json
python -m experiments.db_offload.run --partition heldout --selection experiments/db_offload/protocol/selection.json --track matched --arms A-lexical,A-vector,A-hybrid,A-connected,B-flat,B-connected,C-flat,C-connected,D-flat,D-connected --model-dir data/model --neo4j-home /tmp/writ-bakeoff-tools/neo4j-community-5.26.0 --work data/heldout-matched --output experiments/db_offload/evidence/heldout-matched
```

The final evaluation milestone reports correctness, quality uncertainty, complete
resource profiles, raw failures, independent reranking, review materials, actual
agent trials or their exact missing inputs, and an adoption/rollback decision.
