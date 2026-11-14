# Laptop architecture validation: registered execution protocol

Registered before any laptop scoring, model trial or held-out replication was
run. Commit this file, `registration/*.json` and the harness scripts first;
results go in later commits. Nothing in `experiments/db_offload/` or
`experiments/reliable_memory/` is modified. Their fixtures, evidence and
`preserved.json` registries remain the reference.

## Source and inputs

- Repository main `0511139990775097cbbe59320b7745b7920b52ee` (merge of PR #9).
  `git diff f1b8caa29392f5c5ef61de4bc50e3cf447497e7d 0511139` is empty: the
  merged tree is byte-identical to the reviewed PR #9 head. No open PRs. Five
  older `codex/bakeoff-*`/`phase3` remote branches exist and are left untouched.
  Work happens on branch `laptop-decision` in a separate git worktree.
- Upstream Writ, read-only clone of `https://github.com/infinri/Writ`
  (contains `a0e0e413e3b2…`, `b60bf33983b9…` and V1 `ebdafe5450b2…`). It is
  never checked out, modified or executed.
- Input and harness SHA-256 values: `registration/container-environment.json`
  (`input_sha256`). MiniLM ONNX `6fd5d72f…6046452`, tokenizer `be50c362…572037`.
  Both match `reliable_memory/protocol/settings.json`.
- Pinned runtimes, fetched by `recovery/bootstrap.py`: Neo4j Community 5.26.0
  `ad8ac339…37d7` and Relate FFI 1.0.1 `6d1f6725…98a2`. Both are byte-identical
  to hosted run 43540148638. The Rust thin client (Rust 1.85.1, `--locked`) is
  built locally.

## Environment

Laptop: AMD Ryzen 9 7940HS (8C/16T), 30.7 GiB RAM, Ubuntu 24.04.3, kernel
6.17.0-40, x86_64, normal power profile with frequency scaling active. It is a
shared interactive machine, so isolation is not claimed. Docker 29.1.2 runs a
disposable container (`docker/Dockerfile`): Python 3.12.14, Debian OpenJDK
21.0.13+9 (the hosted run used Temurin 21.0.13+9), Rust 1.85.1, packages from
`requirements-validated.txt` plus `neo4j==5.28.2` and `psutil==7.1.3`. The
container has no cgroup CPU or memory limit. The compose network is pinned to
10.215.0.0/24. Neo4j listens only on the container's 127.0.0.1. Full package
freeze, cgroup limits and rlimits are in `registration/`.

Model trials run on the host (Python 3.12.3), because the existing Claude Code
login lives there. They use Claude Code CLI 2.1.325 with existing authorized
access only. No credentials are created, read or committed, no API key is used,
and no overage is enabled.

## Correctness and replication (stage `correctness`, then `quality`)

`replicate.py correctness` first checks every hash in both `preserved.json`
registries and stops on any drift. It then runs: pytest (149 historical),
five original unittest demos, Phase 3 `reliable_history` (nine scripted
restart/retraction checks), Phase 3 `reliable_demo`, `reliable_memory.audit`
(exact source provenance), `reliable_memory.demo` (17-process canonical
workflow), `db_offload.capability` and `db_offload.recovery.mechanics`
(19 cross-engine gates, ANN oracle, Neo4j restart and paired thin clients).
Everything except the Neo4j harness runs under `scripts/offline_run.py`. The
Neo4j harness is the repository's separate explicit-loopback harness. The
offline boundary is not modified.

`replicate.py quality` reruns the reliable-memory development and held-out
evaluations (frozen settings: k=6, RRF 60, cosine .30, 1600-character
embedding heads, 8,000 bytes / 6,000 codepoints for the entire payload, two
hops / 64 visits, seed 20261114, one warm-up and three repetitions, Latin
rotations). It also reruns the bake-off held-out matched and best tracks
(A–D, including native Neo4j D, frozen `selection.json`: k=20, RRF 60,
gate .30, 16,000 bytes / 12,000 codepoints, seed 20261113). These sets are
**already opened**. They are regression replications, not unseen evaluation,
and nothing is tuned on them. `replicate.py compare` diffs laptop and committed
results per task and arm (payload equality, delivered IDs, target delivery).

## Performance (stage `performance`; no other benchmark or trial jobs running)

1. Cold CLI (`cold_cli.py`): every sample is a fresh process (interpreter,
   network deny, ONNX load, store open, generation/projection validation,
   inference, retrieval, rendering, exit). Profiles are legacy `reliable.agent
   context` hybrid, `grounded_cli --backend flat` and `--backend relate`, over
   the 20 held-out natural-track `a0e0e41` writ-public tasks. Each profile gets two
   warm-up invocations that build its derived caches. Then three repetitions
   run in randomized interleaved order (seed 20261114), 60 samples per
   profile. Peak RSS and CPU are measured per process with `wait4`.
2. Warm persistent: the per-arm timings recorded by the reliable-memory runs
   above. Each arm gets 108 calls, which include inference, export/digest
   validation, DB/index I/O and rendering.
3. Server load: the unchanged bake-off `recovery.suite` (24 profiles: A–D,
   1x/10x/100x, 1/4 readers, 10 warm-ups, target 1,000 samples, 180 s query
   and 300 s outer limits, 2 GiB cooperative RSS budget, Neo4j heap 512 MiB /
   page cache 128 MiB). App, model, DB and worker RSS are counted. Neo4j's
   JVM is included.

Loopback numbers are not remote-server numbers. Laptop, hosted and earlier
timings are different machines and are never treated as paired.

## Model trials (protocol adaptation, fixed-context QA)

`experiments/reliable_memory/agent.py` expects an OpenAI-compatible localhost
endpoint with a `read_context` function tool. The Claude Code CLI cannot add a
custom function tool without an MCP server. Each condition's complete fixed
packet is therefore placed directly in the user message, with the same
structure for every condition. This is **fixed-context QA, not tool-calling,
query rewriting or repository editing**. It cannot establish task completion
or the causal benefit of a rule.

- Tasks: the registered 36 held-out reliable-memory tasks (24 natural
  positives, 6 explicit-source, 3 missing-owner-confirmation, 3
  project-isolation).
- Conditions: A `none` (empty packet), B `legacy-hybrid`, C `grounded-flat`,
  D `grounded-relate`. Packets are the committed repeat-0 payloads in
  `reliable_memory/evidence/heldout/queries.jsonl.gz`, exactly as
  `prepare_review.py` produces them, so trials do not depend on laptop
  numerical differences. Every packet is at or below 8,000 bytes / 6,000
  codepoints. **Neo4j is excluded:** the Neo4j harness serves only the separate
  64-task bake-off corpus. No grounded-memory Neo4j projection exists, so a
  Neo4j condition cannot receive the same inputs or satisfy the canonical
  refresh, retraction and replay contracts. This is reported as missing
  integration, not as a result.
- Model: requested `claude-sonnet-5-5`, effort `low`. The resolved
  identifiers come from the CLI `init` event and `modelUsage`. Temperature,
  seed, top-p and model artifact revision cannot be controlled or observed
  through this host and are recorded as unavailable.
  `CLAUDE_CODE_MAX_OUTPUT_TOKENS=512` is set to match the original 512-token
  allowance. A pilot showed the host does not hard-enforce it (762 tokens), so
  actual output tokens are recorded.
- Isolation: a fresh `claude -p` process per trial with `--safe-mode` (no
  CLAUDE.md, hooks, skills, plugins or user customizations),
  `--setting-sources ''`, `--tools ''` (zero tools), `--strict-mcp-config`
  with an empty MCP config, `--no-session-persistence`,
  `--disable-slash-commands`, `--permission-mode dontAsk` (no bypass flag),
  the original system prompt via `--system-prompt` (adapted only to say the
  packet is supplied in the user message), and a new empty `mktemp` directory
  outside any repository as cwd (the scratchpad path was rejected because its
  name contains the project name). Non-removable host context that remains:
  built-in Claude Code plugins (security, privacy, telemetry, agents-md,
  plugin-authoring) and short host-appended harness guidance. Neither carries
  repository content.
- Order: all 432 (task, condition, repetition) trials are shuffled with
  `random.Random(20261114)`, the same as the original harness. There are
  three paired repetitions. Every attempt is appended to `attempts.jsonl`
  with the full CLI event stream, prompt and packet hashes, usage, the
  reported cost (`costBasis` list price, not a bill) and elapsed time.
  Resumption skips completed trials. A failed trial is retried at most once,
  and both attempts are kept. Stopping condition: a reported quota or rate
  limit stops the run, and actual denominators are published as incomplete.
- Pilot disclosure: three mechanics probes (two self-description prompts and
  one `hel-02`/grounded-flat call) ran before registration. They are excluded
  from all results.

### Scoring (fixed now)

Separate layers are reported: database correctness, retrieval relevance
(target passage delivered in the packet), generated-answer correctness and
task completion. Task completion is **not measured** by fixed-context QA.

- Mechanical: which corpus revisions an answer cites (hex prefix ≥7 of a
  registered revision), whether the task's revision is cited (positives),
  and citations of revisions not present in the packet or request.
- Model-assisted blinded review (`grade.py review`): `claude-opus-5-5`,
  effort low, with the same isolation flags plus structured JSON output. A
  different model from the answerer is used. It sees the question, the
  provisional label, the backend-stripped context and the answer, but not the
  condition or repetition (an empty context still reveals condition A). The
  fixed rubric is `grade.py:RUBRIC`. This is **model-assisted review, not
  independent human review**.
- Blinded human-review materials (`grade.py materials`): shuffled CSV,
  context copies and a separate key. No reviewer is recorded.
- Descriptive comparison only. QA trials carry no adoption gate. With
  model-authored, unreviewed labels they cannot select an architecture.

## Decision gates (unchanged, not weakened)

Bake-off: all correctness gates pass. The paired family bootstrap one-sided
95% lower bound must be > −0.03 for both complete-answer delivery and MRR
(2,000 draws). Adoption also needs ≥1.20x E2E p95 speedup at equivalent
quality and ≤1.10x combined RSS. Reliable memory: zero correctness failures and
noninferiority within 3 points on target-passage delivery, with no superiority
claim on unreviewed labels. An unsupported contract is a failure, never a pass.
If no challenger qualifies, the incumbent default is retained with a concrete
rationale.

## Reproduce

```bash
docker compose -f experiments/laptop_decision/docker/compose.yaml up -d --build
docker compose -f experiments/laptop_decision/docker/compose.yaml exec dev bash -c '
  python scripts/prepare_model.py --output data/model &&
  git clone https://github.com/infinri/Writ /home/dev/Writ-public &&
  python -m experiments.db_offload.recovery.bootstrap --output data/bakeoff-tools &&
  RELATE_FFI_DIR=$PWD/data/bakeoff-tools cargo +1.85.1 build --release --locked \
    --manifest-path experiments/db_offload/rust/Cargo.toml --target-dir data/rust-target &&
  python -m experiments.laptop_decision.replicate correctness &&
  python -m experiments.laptop_decision.replicate quality &&
  python -m experiments.laptop_decision.replicate compare &&
  python -m experiments.laptop_decision.replicate performance'
# Host, with an existing Claude Code login:
python3 -m experiments.laptop_decision.qa_trials --out data/laptop-qa
python3 -m experiments.laptop_decision.grade review --trials data/laptop-qa --out data/laptop-qa-review
python3 -m experiments.laptop_decision.grade materials --trials data/laptop-qa --out data/laptop-qa-human-review
python3 -m experiments.laptop_decision.grade summary --trials data/laptop-qa --review data/laptop-qa-review --out data/laptop-qa-summary
```

AI assistance: this protocol, the harness adapters and the analysis were
written with Claude Code (Claude Opus 5.5). Earlier milestones disclose OpenAI
Codex assistance. Writ/JolliAI attribution in `NOTICE.md` is unchanged.

## Amendment 1 (before any scoring; correctness stage restarted)

The first `correctness` attempt cloned upstream Writ to `data/Writ-public`
inside the checkout. Bare `pytest -q` then collected upstream's `tests/`
package, and 95 collection errors followed (rc=2). This was a setup error and
not a repository failure. The clone now lives outside the checkout at
`/home/dev/Writ-public`. The interrupted attempt's logs are kept in the
container under `data/laptop-results-attempt1-invalid/` and are not used. The
whole stage reruns fresh. No test, fixture, setting or gate changed. QA trials
were already running from the committed packets and are unaffected.

## Amendment 2: corrected model-assisted grading (registered after the original review, before regrading)

**Defect.** For blinding, the registered review removed `projection`,
`snapshot.generation`, `encoder_id` and `selection_policy` from the context the
grader saw, but the answering model saw the complete packet. When an answer
correctly quoted a removed field (for example `permitted_rows: 0`, the
`unrelated-project` projection or the generation digest), the grader counted it
as unsupported. 17 of 21 grounded-flat and 17 of 20 grounded-relate answers
flagged with unsupported claims cite removed fields, against 7 of 12 for legacy
hybrid. The unsupported-assertion metric is therefore biased against the
grounded conditions, and other rubric fields may also be affected.

**Preserved unchanged.** The original grader code is in commits up to
`0e3e602`. The original verdicts are in `evidence/qa-model-review/` (hashes in
`SHA256SUMS`) and the original summary in `evidence/qa-summary-original/`.
`grade.py inputs --context stripped` regenerates all 432 original grader
inputs, and their SHA-256 values match the recorded `prompt_sha256` (0
mismatches, `grader-inputs-stripped.jsonl.gz`).

**Corrected review.** `grade.py review --context full` regrades all 432
answers. The grader model, effort, system prompt, rubric, schema, isolation
flags and seed-shuffled order are unchanged. The grader sees the exact packet
supplied to the answerer, with only `projection.backend` (`flat` or `relate`,
the only condition-naming field) replaced by `[condition-redacted]`. No answer
text names a backend. An empty packet still reveals condition A, and the
legacy and grounded packet formats remain distinguishable. Output goes to
`evidence/qa-model-review-corrected/`. Original and corrected scores are
reported side by side and never merged. Both remain model-assisted review, not
independent human review.

**Analysis (`grade.py compare`).** Results are split into natural-language
(`section-question`), historical, explicit-source and unknown controls
(missing-owner-confirmation plus project-isolation). The primary per-answer
score is correct 1 / partial .5 / incorrect 0 for positives, and 1 for an
unknown control when the answer warrantedly declines. Repetitions are paired
within each task: the three repetitions are averaged per task, task-level
differences are taken against grounded-flat and legacy-hybrid, and a 2,000-draw
task bootstrap (seed 20261115) gives descriptive 95% intervals. Repetition-level
better/worse counts are also reported. Grader and answerer token usage and
CLI-reported list-price cost are summed. Actual billing is unknown. No adoption
gate depends on these QA results.
