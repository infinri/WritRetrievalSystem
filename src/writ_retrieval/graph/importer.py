"""Import the pinned, line-oriented Writ corpus into a NEW persistent directory.

This intentionally accepts only the shipped baseline dump, not arbitrary Cypher
or a general Neo4j backup. Failure discards staging; existing stores are untouched.
"""
import hashlib
from pathlib import Path
import tempfile

import relate

CORPUS_SHA256 = "cc34b71a9c7c1eddc06b8ba296b78a3b2c3fec151847eee088399095134d9e96"


def import_corpus(source: Path, store: Path) -> dict:
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != CORPUS_SHA256:
        raise ValueError("Corpus does not match the pinned Writ V1 baseline dump")
    if store.exists():
        raise FileExistsError(f"Store already exists: {store}. Choose a new directory.")
    store.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".writ-import-", dir=store.parent) as temp:
        stage = Path(temp) / "graph"
        db = relate.connect(str(stage))
        try:
            for number, line in enumerate(payload.decode().splitlines(), 1):
                try:
                    db.execute(line)
                except Exception as exc:
                    raise RuntimeError(f"Corpus import failed at statement {number}: {exc}") from exc
            nodes = list(db.execute("MATCH (n) RETURN count(n) AS count"))[0]["count"]
            edges = list(db.execute("MATCH ()-[r]->() RETURN count(r) AS count"))[0]["count"]
        finally:
            db.close()
        stage.rename(store)
    return {"store": str(store), "nodes": nodes, "edges": edges, "source_sha256": CORPUS_SHA256}
