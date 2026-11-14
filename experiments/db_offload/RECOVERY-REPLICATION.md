# Executable hosted replication after workspace loss

The primary new-host replication is Actions run **43540148638**, from source
cfd54b9dfdc4deb257642c328a125e0395aa6b6a. This designation was made while its
quality job was still in progress, before inspecting any hosted results; it is
not a choice of the fastest run. The earlier push-triggered run is a separate
bring-up replication if it produces evidence. Preserve it as such.

The original local execution environment became unavailable. PRs #4/#5/#6 and
their raw development evidence were already published. Local held-out/reranker/
native-gate results completed, but their unpushed raw files cannot be recovered
with currently available tools. Do not reconstruct or cite them as delivered raw
evidence. The last 24-profile suite's final state is unknown (at least sixteen
finished, including failures). recovery/STATUS.md records this boundary.

This workflow reruns identical frozen data, ranking policies and pre-held-out
selection on a new hosted machine. It does not tune against opened held-out data
or provide a second unseen test set. Hardware, libraries, runtime/archive hashes,
commands, failures and measured costs are saved with the new results. The public
MiniLM artifacts remain pinned; numerical equivalence to Writ's original missing
local export remains unverified.

## Run from a checkout

Use a fresh Linux Python 3.12 venv, GCC/G++, Java 21.0.13 and Rust 1.85.1:

~~~sh
CC=gcc CXX=g++ HNSWLIB_NO_NATIVE=1 pip install --no-cache-dir --no-binary=hnswlib -c requirements-validated.txt -e '.[dev]' -r experiments/db_offload/requirements.txt
python scripts/prepare_model.py --output data/model
python -m experiments.db_offload.recovery.bootstrap --output data/bakeoff-tools
rustup toolchain install 1.85.1 --profile minimal
RELATE_FFI_DIR="$PWD/data/bakeoff-tools" cargo +1.85.1 build --release --locked --manifest-path experiments/db_offload/rust/Cargo.toml
python -m experiments.db_offload.recovery.runner --root data/new-quality-results --tools data/bakeoff-tools
python -m experiments.db_offload.recovery.runner --performance --root data/new-quality-results --tools data/bakeoff-tools
~~~

Work/output paths must be fresh, including the runner's data/recovery-* work
directories. This is an isolated comparison harness, not the supported offline
agent command. Native Neo4j is an owned literal-loopback child; model inference
still runs inside scripts/offline_run.py. No privileged host change, remote
database, new external credential or paid model service is required.

The workflow checkpoints quality before the long suite. It publishes only the
new experimental evidence directory to a unique codex/bakeoff-evidence-RUN_ID
branch, without force pushing or merging production code. The source workflow is
guarded to the registered source SHA after starting the primary run, preventing
expensive reruns caused by subsequent report-only PR updates. Reproduction by CLI
remains available; an intentionally new hosted run needs its own explicit source
registration.

## Scoring and limitations

64 formulations / 32 families, 32 tasks per partition, 20 positive and twelve
unknown held-out controls. The positive labels cover only five distinct source
versions; proxy qualifications are unreviewed. Every actual target prefix must
be delivered with exact version/digest; an unqualified source URI hit is not
sufficient. The complete_answer field is proxy completeness, not independently
adjudicated answer sufficiency. Empty-context abstention is a retrieval metric,
not a live model's abstention. Review labels.csv against wider public sections.

Raw per-query rankings, full payloads, omissions, errors, latency and exact gold
references are retained. Reports use paired topic-family bootstrap uncertainty
(2,000 draws, one-sided 95% lower bounds, -0.03 margins) and publish every changed
task. Original weighted corpus and reliable restart/retraction tests are separate
historical controls. Mandatory rule delivery is not ranked rule recall; all
original exclusions and fixtures remain untouched.

Warm profiles use prepared static generations, uncached inference, native/
application fusion as assigned, validation and whole-payload assembly. Live
canonical refresh is not implemented. Model queue time and all observed app/
model/DB/worker RSS are counted. Four active readers share one serialized model.
Their warmup can retain an extra idle native reader connection: this is a measured
prototype overhead and limits minimal-footprint comparisons. No such overhead
is silently subtracted. The 2 GiB RSS budget is cooperative (after setup/during
queries), not an OS limit during import. CPU totals include SELF and waited
CHILDREN; unwaited descendants can be incomplete. Working disk excludes shared
runtime/model footprints, which are separately recorded where measured; full
Java/interpreter deployment disk remains unmeasured.

The 1x/10x/100x load uses 188 current units and deterministic tiny-jitter copies,
not 100x real semantic evidence or 100x embedding cost. Target 1,000 samples after
ten warmups, 180-second query budget, 300-second outer setup/query/shutdown cap.
Failed profiles keep available partial samples but receive no adoption
percentiles. One run/profile and raw empirical p99 are not cross-host assurances.
Exact-vector oracle recall is separate from semantic relevance; native analyzer
metadata does not imply equivalent scores. Strict native selection overrequests
the permitted partition for tie handling; raw ANN curves use actual top-k.

Thin Rust clients retain Python outer validation and model/rendering. The paired
microbenchmarks randomize order, use 200 measured pairs and ten warmup pairs, and
record equivalent selections. Relate PyO3 versus C ABI and HTTP client differences
remain confounds; no full Rust context pipeline or language-only speed is claimed.

Learned reranking is a separate fixed local Apache-2.0 cross-encoder ablation,
twenty candidates, 384 pair tokens, batch eight, two/one ORT threads. No threshold
tuning. Its added cost and worker memory are measured independently. Composed
latency is not directly measured whole-system reranking latency/combined RSS.

The live generative agent experiment is NOT RUN unless an authorized local host
and exact model identity/revision are supplied. A real tool-calling harness,
paired repetitions, fixed prompts/tools/budgets, traces and blind materials are
prepared. Packet mode does not pretend to run fresh adaptive search. For actual
execution, decompress review/agent-packets.json.gz if needed, then use:

~~~sh
WRIT_BAKEOFF_AGENT_ENDPOINT=http://127.0.0.1:8000/v1 WRIT_BAKEOFF_AGENT_MODEL=EXACT_MODEL_ID python -m experiments.db_offload.recovery.agent --packets data/agent-packets.json --output data/new-agent-trials
~~~

No owner approval or execution authorization is an agent tool.

## Attribution

Original Writ MIT and Lucio Saldivar/JolliAI credits in NOTICE.md remain intact.
The experiment reuses Writ's encoder, Tantivy wrapper, contracts, fixtures and
public source text at the frozen revisions. Relate 1.0.1 Python/C ABI is external
Apache-2.0; Neo4j Community 5.26.0 is an external GPL runtime. Native binaries are
not bundled or relicensed. Rust dependencies are locked; MiniLM and the independent
cross-encoder retain their pinned Apache-2.0 model cards. OpenAI Codex assisted
code, provisional labels and analysis. No independent human review is implied.
