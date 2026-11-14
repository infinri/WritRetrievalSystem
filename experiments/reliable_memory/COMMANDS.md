# Run the opt-in workflow

Use Python 3.12 on Linux x86_64. From the repository root:

```bash
python -m pip install -c requirements-validated.txt -e '.[dev]'
python scripts/prepare_model.py --output data/model
git clone --single-branch --branch v2/architecture-rebuild https://github.com/infinri/Writ ../Writ-public
python scripts/offline_run.py -m pytest -q
python scripts/offline_run.py -m unittest discover -s tests -v
python scripts/offline_run.py -m experiments.reliable_memory.audit \
  --repo ../Writ-public --out data/passage-provenance.json
```

Clone/model preparation is online and explicit. Everything below is local; ingestion reads exact objects and never checks out or executes upstream code. Keep the upstream checkout read-only. Use fresh work and result directories for each run.

```bash
python scripts/offline_run.py -m experiments.reliable_memory.run \
  --model-dir data/model --work-dir data/reliable-dev \
  --out data/reliable-dev-results --split development
python scripts/offline_run.py -m experiments.reliable_memory.run \
  --model-dir data/model --work-dir data/reliable-heldout \
  --out data/reliable-heldout-results --split heldout
python scripts/offline_run.py -m experiments.reliable_memory.analyze \
  --results data/reliable-heldout-results/queries.jsonl.gz \
  --out data/reliable-heldout-results/comparison.json
python scripts/offline_run.py -m experiments.reliable_memory.demo \
  --repo ../Writ-public --model-dir data/model \
  --work-dir data/reliable-demo --out data/reliable-demo-results
```

The frozen held-out set has now been opened. It is a regression set for future work. Do not tune against it and then claim unseen evaluation; freeze a new set first. `freeze.py --repo PATH` reproduces input preparation, not a way to overwrite gold while retaining its old evidence claims.

## Supported owner capture, offline context and inspection

```bash
python -m writ_retrieval.reliable.cli --store data/local-memory passage-ingest \
  --repo ../Writ-public --revision a0e0e413e3b20082a85e7d75c58b45b0ba09b903 \
  --path docs/architecture/retrieval-and-memory.md --project writ-public --create
python -m writ_retrieval.reliable.grounded_cli \
  --store data/local-memory --model-dir data/model --cache-dir data/local-indexes \
  --project writ-public --backend relate --arm hybrid \
  'What distinguishes retrieved guidance from execution permission?'
```

`grounded_cli` installs the same network deny as the legacy read-only agent before loading third-party runtimes. Default backend is `flat`; native `relate` is opt-in. Use `--request request.json` for exact source/binding, history and evidence requirements described in CONTRACTS.md. Use `--require KEY_TOKEN` for hard required records and `--max-bytes/--max-chars` for the entire payload. `--inspect` returns owner diagnostics; give a model only the wrapper's `payload`.

Capture/feedback/claim/retraction/lifecycle commands remain `reliable.cli`, using the Phase 3 contracts and actual local-owner terminal for confirmation/review. Those commands are absent from the grounded agent. Existing `reliable.agent context/inspect`, weighted `writ-retrieval query`, and Phase 2 connected/recall commands remain unchanged controls.

Read exact versions with the legacy read-only inspector, using a grounded cache directory and returned generation:

```bash
python -m writ_retrieval.reliable.agent --store data/local-memory inspect \
  '{"project":"writ-public","label":"Claim","id":"EXACT_ID_FROM_CONTEXT"}' \
  --project writ-public --generation sha256:EXACT_GENERATION --cache-dir data/local-indexes
```

For a corrupt derived index: stop the context process, take the exact projection identity from diagnostics/pointer, quarantine it through the owner CLI, then rerun context. Keep canonical data intact.

```bash
python -m writ_retrieval.reliable.cli --store data/local-memory projection-quarantine \
  --cache-dir data/local-indexes --identity sha256:EXACT_PROJECTION_ID
```

## Review and actual generative trials

```bash
python scripts/offline_run.py -m experiments.reliable_memory.prepare_review \
  --results data/reliable-heldout-results/queries.jsonl.gz --out data/new-review
python scripts/offline_run.py -m experiments.reliable_memory.agent \
  --packets data/new-review/agent-packets.json.gz --out data/agent-status
```

The last command records NOT RUN without a generative host. Once explicitly authorized, run the **separate experimental** harness outside the offline agent with `--endpoint http://127.0.0.1:PORT/v1 --model EXACT_MODEL --model-revision IMMUTABLE_REVISION`. It only accepts localhost; existing offline controls are unchanged. Four profiles (no history, legacy hybrid, grounded flat, grounded Relate), identical prompts/tools/one-packet allowance/budgets, three paired repetitions and fixed seeds. It records actual model responses, usage if supplied, errors and traces; costs remain unknown if the host does not report billing. It is fixed-context QA, not query rewriting or repository-editing task execution. Human review of responses is still required.
