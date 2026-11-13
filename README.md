# Writ Retrieval System

Connected context for AI agents, built on Writ's retrieval and decision-memory foundation and adapted to Relate.

## Current milestone

A working embedded Relate integration that persists a small synthetic graph and retrieves a file change's motivating decision, governing rule, and commit. No Neo4j server or model download is needed for this milestone.

The full Writ hybrid retrieval pipeline has not been extracted yet. This demo does not perform semantic search, execute agent actions, enforce policy, or prove that a rule was followed.

## Run

Python 3.11 or later is required. Verified on Python 3.12.14, Linux x86_64, with `relate-db==1.0.1`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
writ-retrieval init-demo
writ-retrieval context src/payments.py
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell.

`init-demo` creates a persistent directory at `data/demo`; the next command opens that directory in a new process. Pass `--store PATH` to either command to choose another directory. Rerunning the seed merges the same fixture instead of duplicating it. The sample is fictional and contains no user records.

The result includes:

```json
{
  "path": "src/payments.py",
  "change_id": "CHANGE-001",
  "decision_id": "DEC-001",
  "rationale": "Parameterize the payment lookup to keep user input out of SQL syntax.",
  "rule_id": "PARAM-001",
  "rule": "Use parameterized SQL queries.",
  "commit_id": "COMMIT-001",
  "commit_subject": "Parameterize payment lookup"
}
```

The graph connects `FileChange -MOTIVATED_BY-> Decision -GOVERNED_BY-> Rule`, with `Commit -INCLUDES-> FileChange`. Queries explicitly filter each matched node by project. This is a local demo, not authenticated multi-tenant isolation.

## Verify

```bash
python -m unittest discover -s tests -v
```

Four real-engine integration checks cover separate-process persistence, repeated seeding, unknown paths/other projects, and missing-store handling. See [validation](docs/VALIDATION.md).

## Next

Extract the scoped hybrid retrieval baseline, adapt its graph reads to Relate, and compare lexical/vector retrieval with and without graph expansion on the same queries. See [the extraction plan](docs/EXTRACTION-PLAN.md).

## Origin and contest work

This project builds on [infinri/Writ](https://github.com/infinri/Writ), baseline commit `ebdafe5450b201339f81e717ed104e6bcfd3fe3e`. Writ's retrieval and decision-memory concepts predate this entry. The Relate demo, packaging, and integration checks here are new work; no Writ source modules have been copied into this initial milestone. Copied modules and their existing credits will be recorded as extraction proceeds.

Development assistance: OpenAI Codex assisted with repository inspection, implementation, documentation, and test execution. Human review and the final contest submission are pending.

Contest: [Relate by Neo4j Hackathon](https://relate.devpost.com/). This repository is an early implementation, not a completed submission. Licensed under [MIT](LICENSE).
