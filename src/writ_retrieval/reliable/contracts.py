"""Closed versioned contracts; hashes bind bytes, never confer source authority."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from writ_retrieval.graph.identity import Key

DIGEST = r"^sha256:[0-9a-f]{64}$"


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def digest(value): return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()
def text_digest(value): return "sha256:" + hashlib.sha256(value.encode()).hexdigest()
def now_utc(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def instant(value):
    if not isinstance(value,str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise ValueError("time requires UTC whole seconds YYYY-MM-DDTHH:MM:SSZ")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def revision(value):
    if type(value) is not int or not 0 <= value <= 2**53-1: raise ValueError("invalid integer revision")
    return value


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Source(Closed):
    contract_version: Literal["writ-source/1"] = "writ-source/1"
    uri: str = Field(min_length=1, max_length=2000)
    revision: str = Field(min_length=1, max_length=256)
    path: str | None = None
    committed_at: str | None = None
    start_line: StrictInt | None = Field(default=None,ge=1)
    end_line: StrictInt | None = Field(default=None,ge=1)

    @field_validator("committed_at")
    @classmethod
    def calendar(cls,v):
        if v is not None: instant(v)
        return v


    @model_validator(mode="after")
    def git_binding(self):
        if self.start_line and self.end_line and self.end_line < self.start_line: raise ValueError("inverted source lines")
        if self.uri.startswith("https://github.com/") and ("/blob/" in self.uri or "/commit/" in self.uri):
            match=re.search(r"/(?:blob|commit)/([0-9a-f]{40})(?:/|#|$)",self.uri)
            if not match or match.group(1)!=self.revision: raise ValueError("source URI/revision binding mismatch")
            if "/blob/" in self.uri and self.path and self.uri.split("/blob/",1)[1].split("/",1)[1].split("#",1)[0]!=self.path: raise ValueError("source URI/path mismatch")
        return self


class Binding(Closed):
    ref: dict
    revision: StrictInt = Field(ge=1, le=2**53-1)
    content_digest: str = Field(pattern=DIGEST)

    @field_validator("ref")
    @classmethod
    def identity(cls,v): Key.parse(v); return v


class Temporal(Closed):
    recorded_at: str
    valid_from: str | None = None
    valid_to: str | None = None

    @field_validator("recorded_at", "valid_from", "valid_to")
    @classmethod
    def calendar(cls,v):
        if v is not None: instant(v)
        return v

    @model_validator(mode="after")
    def interval(self):
        if self.valid_from and self.valid_to and instant(self.valid_from) >= instant(self.valid_to): raise ValueError("empty/inverted validity interval")
        return self

    def check_at(self, now):
        if instant(self.recorded_at) > instant(now): raise ValueError("future recorded time")


class Claim(Temporal):
    contract_version: Literal["writ-claim/1"] = "writ-claim/1"
    project: str = Field(min_length=1, max_length=256)
    claim_id: str = Field(min_length=1, max_length=256)
    topic: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1,max_length=1024)
    text: str = Field(min_length=1,max_length=64000)
    content_digest: str = Field(pattern=DIGEST)
    source: Source
    kind: Literal["model_assertion", "repository_assertion"]
    rationale: str | None = None

    @model_validator(mode="after")
    def bytes_match(self):
        if self.source.committed_at and instant(self.recorded_at)<instant(self.source.committed_at): raise ValueError("claim recorded before its source revision")
        if text_digest(self.text) != self.content_digest: raise ValueError("claim content digest mismatch")
        return self


class Evidence(Temporal):
    contract_version: Literal["writ-evidence/1"] = "writ-evidence/1"
    project: str = Field(min_length=1, max_length=256)
    evidence_id: str = Field(min_length=1, max_length=256)
    subject: Binding
    source: Source
    material: str = Field(max_length=64000)
    content_digest: str = Field(pattern=DIGEST)
    kind: Literal["model_assertion", "repository_assertion"]

    @model_validator(mode="after")
    def bytes_match(self):
        if self.source.committed_at and instant(self.recorded_at)<instant(self.source.committed_at): raise ValueError("evidence recorded before its source revision")
        if text_digest(self.material) != self.content_digest: raise ValueError("evidence content digest mismatch")
        return self


# Deliberately do not hash mutable materializations or approval provenance into a claim's text meaning.
VOLATILE = {"revision", "status", "superseded", "superseded_by", "times_seen_positive", "times_seen_negative",
            "provenance", "authority", "source_origin", "claim_hash", "proposal_hash", "content_hash",
            "verification_status", "verified_at", "verified_by", "verification_scope", "retracted_at", "retraction_reason",
            "legacy_positive", "legacy_negative", "feedback_policy", "judgment_kind", "review_eligible", "review_flagged", "approval_status", "graduated_via"}


def subject_digest(node): return digest({k:v for k,v in node.items() if k not in VOLATILE})
def binding_for(key,node):
    return Binding(ref=key.as_dict(), revision=revision(node.get("revision",0)), content_digest=subject_digest(node)).model_dump()


def window_active(node, at):
    try:
        if node.get("recorded_at") and instant(node["recorded_at"]) > instant(at): return False
        if node.get("valid_from") and instant(at) < instant(node["valid_from"]): return False
        if node.get("valid_to") and instant(at) >= instant(node["valid_to"]): return False
        return True
    except ValueError: return False


def binding_matches(binding, nodes):
    try:
        b=Binding(**binding); key=Key.parse(b.ref); node=nodes.get(key)
        return node is not None and b.revision == node.get("revision",0) and b.content_digest == subject_digest(node)
    except (ValueError,TypeError): return False
