# Validation

Initial milestone, 2026-11-13.

Environment: Python 3.12.14, Linux x86_64, `relate-db==1.0.1` installed from its published wheel. Project installed with `python -m pip install -e .` in a clean virtual environment.

Command: `python -m unittest discover -s tests -v`.

Result: **4 tests passed** against the actual embedded Relate engine:

- A seed process exits; a separate process reopens the persistent directory and retrieves the complete decision/rule/commit chain.
- Repeating the fixture seed produces one context result rather than duplicate relationships.
- An unknown path and a different project return no context.
- Querying a missing store raises a clear error without creating a new database.

Also executed both documented CLI commands successfully: `writ-retrieval init-demo` and `writ-retrieval context src/payments.py`.

These checks establish only this synthetic graph's creation, persistence and traversal behavior. Full Writ pipeline extraction, corpus import, ranking parity, cross-project adversarial tests, performance measurements and judge-install verification are pending.
