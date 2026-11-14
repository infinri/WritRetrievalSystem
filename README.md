# Writ Retrieval System

Connected context for AI agents, extracted from Writ V1 and adapted to embedded Relate.

The standalone baseline runs BM25 (Tantivy), vector search (HNSW + MiniLM ONNX),
bounded graph enrichment, weighted ranking, filtering, abstention and context
budget selection. Decision and memory recall is a separate path. No Neo4j server,
Bolt driver, agent host or Writ V2 kernel is required.

## Opt-in canonical memory indexes

A follow-up adds persistent native Relate projections from the canonical memory
ledger, full-text context cards and explicit source/evidence requirements. The
existing retrieval paths remain controls. See [commands](experiments/reliable_memory/COMMANDS.md),
[contracts](experiments/reliable_memory/CONTRACTS.md) and [measured findings](experiments/reliable_memory/FINDINGS.md).
On the provisional held-out natural-language subset, grounded flat/native deliver
20/24 labeled passages versus legacy hybrid’s 19/24; development regresses
15/24 versus 17/24. Native is slightly slower at the median. This does not establish a graph advantage or better agent outcomes.
Human review and actual generative trials remain pending.

## Reliable versioned context (Phase 3)

A separate local path binds guidance, memory, evidence and rendering to one
published snapshot generation. It adds revision-bound source contracts, explicit
retraction/conflicts, replay-safe active evidence, and one complete UTF-8/character
budget. A read-only agent CLI can inspect exact historical versions; owner approval
remains a separate terminal action. Linux single-thread/single-writer support only.

See [runnable Phase 3 commands](docs/PHASE3.md), the [V2 scope map](docs/phase3/V2-SCOPE-MAP.md),
[contracts](docs/phase3/CONTRACTS.md) and [findings](docs/phase3/FINDINGS.md).
The real-history experiment is deliberately reported without a graph-advantage
claim: connected covers 3/10 target source versions versus flat hybrid's 4/10.
Labels remain unreviewed; no generative-agent outcome experiment was run.
Historical Phase 3 validation is **117 pytest checks**, five original demo checks and nine
scripted restart/retraction checks. Original
weighted retrieval and all Phase 1/2 fixtures/evidence remain available below.

## Connected memory and feedback

Phase 2 adds transactional capture for decisions, changes, commits, memories and
outcomes; qualified graph identity; bounded cited-history context; durable
positive/negative feedback; and an explicit local-owner proposal review workflow.
Decision/memory recall remains separate from rule candidates.

```bash
python -m writ_retrieval.evaluation.scenario --store data/my-phase2-run --output data/my-phase2-evidence
writ-retrieval connected 'SQL parameters src/payments.py' --store data/my-phase2-run --model-dir data/model --project payments --project-root .
```

Install dependencies and prepare the model below first. The scenario needs a new
store and writes synthetic records, evidence and a review artifact. See
[Phase 2 commands and contracts](docs/PHASE2.md) and the concise
[findings report](docs/FINDINGS.md). **94 tests pass.** Full-corpus outputs are
unchanged across 1,012 paired query runs; the synthetic scenario demonstrates
persistent history retrieval and the documented confidence update, not improved
real-world outcomes.

## Install and verify

Python 3.11 or later; verified on Python 3.12, Linux x86_64. Building `hnswlib`
requires a C++ compiler and Python development headers. On Linux, install the
platform's build tools first; if Python names an unavailable compiler, use
`CC=gcc CXX=g++` for the install command.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-validated.txt -e '.[dev]'
python -m pytest -q
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. Windows is not validated
by this milestone; the C++ build toolchain may require separate setup.

Tests use actual Relate, Tantivy and HNSW with controlled vectors, and do not
download a model. `requirements-validated.txt` records the tested dependency set.
The original demo can still be checked with `python -m unittest discover -s tests -v`.

## Run hybrid rule retrieval

From the repository root:

```bash
writ-retrieval import-corpus tests/fixtures/writ-corpus.cypher --store data/corpus
python scripts/prepare_model.py --output data/model
writ-retrieval query 'controller contains SQL query' --store data/corpus --model-dir data/model --project example
```

The importer accepts only the SHA-256-verified baseline dump and a new destination.
It stages the import and publishes the persistent directory after success. It
imports 468 nodes and 1,268 relationships without changing corpus content.
Subsequent CLI invocations reopen the graph and reuse persisted indexes.

Model setup downloads a pinned public MiniLM export and tokenizer, checks hashes,
and retains the model README and manifest. It requires network access. Runtime
queries need no network. Weights are not bundled. The CLI separates index caches
by model/tokenizer bytes; pass `--cache PATH` to choose the parent directory.

`query` uses the original rule-injection abstention threshold **0.30**. Its factory
API remains ungated by default, as upstream intended for authoring/diagnostics;
CLI `--ungated` explicitly opts into that behavior. Other options include
`--mode literal` and `--budget 600`. JSON includes selected rule IDs, scores,
mode, raw similarity signal and scoped relationships. There is no generative
answer or authorization decision.

Python callers can use `RelateGraph`, `load_pipeline_inputs`, `assemble_pipeline`
and `build_pipeline`, injecting an encoder through `embedding_model`. Set
`WRIT_RETRIEVAL_CACHE` and, for default model discovery,
`WRIT_RETRIEVAL_MODEL_DIR`. Library callers must isolate caches when switching
encoders. Embedded graph reads are synchronous startup operations behind an
async API, not a ready-to-deploy concurrent web service.

## Run the persistent decision demo and recall

```bash
writ-retrieval init-demo
writ-retrieval context src/payments.py
writ-retrieval recall src/payments.py --project writ-demo --project-root . --full
```

`init-demo` creates or updates `data/demo`. Rerun it to add canonical V1 identity
properties to a store made by the initial milestone; the original `context`
output remains the same. `--store PATH` chooses another persistent directory.
The fictional graph connects `FileChange -MOTIVATED_BY-> Decision -GOVERNED_BY-> Rule`
and `Commit -INCLUDES-> FileChange`.

Recall ranks project decisions by named path, BM25 terms and then recency. Its
budgeted cards preserve decision IDs and governing rule IDs; `--full` also reads
rule statements. Use `--matched-only` to disable recency fill. A cited rule is
attribution, not proof that an action complied with it.

## Scope and evidence

Writ's existing policy is preserved: Rule plus five methodology types are shared
doctrine; other node types are records, visible to their project or `_shared` in
retrieval. Decision recall uses exact project reads. An absent caller project
does not disable the retrieval visibility filter. These are local data-selection
rules, not authenticated multi-tenant isolation.

[Validation](docs/VALIDATION.md) records controlled upstream parity, real-engine
checks, a full-corpus ONNX query and remaining gaps. [The extraction plan](docs/EXTRACTION-PLAN.md)
tracks later connectivity and evaluation work. No ranking, speed or relevance
improvement is claimed. Fixture eligibility can be inspected without quality claims:

```bash
python scripts/audit_fixture_targets.py --store data/corpus
```

## Origin and contest work

Reuses [Writ V1](https://github.com/infinri/Writ), commit
`ebdafe5450b201339f81e717ed104e6bcfd3fe3e`, by Lucio Saldivar, under [MIT](LICENSE).
The Relate adaptation and extraction validation are this entry's work. See
[attribution](NOTICE.md) for reused modules, JolliAI credit and AI assistance.

[Relate by Neo4j Hackathon](https://relate.devpost.com/). Human review and final
submission requirements remain pending.
