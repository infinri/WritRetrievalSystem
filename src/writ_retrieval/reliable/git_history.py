"""Read public Git objects without checkout, hooks, network access or repository writes."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

PUBLIC_REPOSITORY = "https://github.com/infinri/Writ"
PATHS = (
    "docs/implementation/DECISION-LOG.md", "docs/implementation/M3-05-TRANSITION-SERVICE.md",
    "docs/implementation/WORK-STATE.md", "docs/architecture/retrieval-and-memory.md",
    "docs/architecture/data-model.md", "docs/implementation/M3-ACCEPTANCE-CONTRACTS.md",
)


def git(repo, *args):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1"}
    return subprocess.check_output(["git", "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args], env=env)


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_id(revision, path, anchor):
    return f"{PUBLIC_REPOSITORY}/blob/{revision}/{path}#{anchor}"


def sections(path, text):
    matches = list(re.finditer(r"(?m)^## (.+)$", text))
    spans = [("Document introduction", 0, matches[0].start() if matches else len(text))]
    spans += [(m.group(1), m.start(), matches[i+1].start() if i+1<len(matches) else len(text)) for i,m in enumerate(matches)]
    for heading, start, end in spans:
        if path.endswith("DECISION-LOG.md") and not any(heading.startswith(f"D-{n:03d}:") for n in (33,34,35,36)):
            continue
        body = text[start:end].strip()
        if not body: continue
        anchor = hashlib.sha256(heading.encode()).hexdigest()[:16]
        yield {"heading": heading, "anchor": anchor, "text": body, "digest": hashlib.sha256(body.encode()).hexdigest(),
               "start_line": text[:start].count("\n")+1, "end_line": text[:end].count("\n")+1}


def export_history(repo, end, *, limit=12, recorded_at=None):
    if not re.fullmatch(r"[0-9a-f]{40}", end): raise ValueError("end must be a full Git object revision")
    if not 1 <= limit <= 64: raise ValueError("history limit must be 1..64")
    resolved = git(repo, "rev-parse", "--verify", end+"^{commit}").decode().strip()
    if resolved != end: raise ValueError("revision binding mismatch")
    license_text = git(repo, "show", end+":LICENSE").decode()
    if "MIT License" not in license_text: raise ValueError("expected redistributable MIT source")
    recorded_at = recorded_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    revisions = git(repo, "rev-list", "--first-parent", f"--max-count={limit}", end).decode().splitlines()[::-1]
    documents = []; commits = []; previous = {}
    for revision in revisions:
        fields = git(repo, "show", "-s", "--format=%H%x00%cI%x00%s%x00%b", revision).decode().rstrip("\n").split("\x00",3)
        paths = git(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", revision, "--", *PATHS).decode().splitlines()
        commits.append({"revision": revision, "committed_at": utc(fields[1]), "subject": fields[2], "body": fields[3], "paths": paths,
                        "rationale": None, "approval": "unknown", "outcome": "unknown"})
        # Initial source snapshot plus changed files only. Facts are source bytes, not approval assertions.
        for path in PATHS:
            if revision != revisions[0] and path not in paths: continue
            spec = revision+":"+path
            exists = subprocess.run(["git", "--no-replace-objects", "-C", str(repo), "cat-file", "-e", spec], capture_output=True).returncode == 0
            if not exists: continue
            material = git(repo, "show", spec).decode()
            blob = git(repo, "rev-parse", spec).decode().strip()
            for section in sections(path, material):
                key = (path,section["anchor"])
                if previous.get(key) == section["digest"]: continue
                previous[key] = section["digest"]
                documents.append({**section, "path": path, "revision": revision, "blob_id": blob, "committed_at": utc(fields[1]),
                                  "uri": source_id(revision,path,section["anchor"]), "source_kind": "repository_assertion", "verification_status": "unverified"})
    return {"contract_version": "writ-git-history/1", "repository": PUBLIC_REPOSITORY, "end": end, "recorded_at": recorded_at,
            "commits": commits, "documents": documents, "license": license_text,
            "limits": {"first_parent_commits": limit, "paths": list(PATHS)},
            "unknowns": "Commit metadata is not approval, rationale, successful tests or verification of repository assertions."}
