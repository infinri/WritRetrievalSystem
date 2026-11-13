"""Standalone artifact locations; no dependency on Writ's host configuration."""
import os
from pathlib import Path


def get_hnsw_cache_dir() -> str:
    return str(Path(os.environ.get("WRIT_RETRIEVAL_CACHE", Path.home() / ".cache" / "writ-retrieval")) / "hnsw")
