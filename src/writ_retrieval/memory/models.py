"""Capture contracts adapted from Writ V1 record models; records never become rules."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(min_length=1)
    ts: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    session_id: str = ""

    @field_validator("project", "ts")
    @classmethod
    def clean(cls, value):
        if not value.strip() or "\x00" in value: raise ValueError("empty or NUL field")
        return value

    @field_validator("source_refs")
    @classmethod
    def sources(cls, value):
        if any(not item.strip() for item in value): raise ValueError("blank source reference")
        return value


class Decision(Record):
    decision_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    planned_files: list[dict] = Field(default_factory=list)
    governing_rule_ids: list[str] = Field(default_factory=list)
    rule_refs: list[dict] = Field(default_factory=list)
    phase: str = "recorded"


class FileChange(Record):
    change_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    change_type: Literal["add", "modify", "delete", "rename"] = "modify"
    reason: str = Field(min_length=1)
    queried_rule_ids: list[str] = Field(default_factory=list)
    cited_rule_ids: list[str] = Field(default_factory=list)
    commit_hash: str | None = None
    decision_refs: list[dict] = Field(default_factory=list)


class Commit(Record):
    commit_hash: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    author: str = ""
    branch: str = ""
    change_refs: list[dict] = Field(default_factory=list)
    decision_refs: list[dict] = Field(default_factory=list)


class Memory(Record):
    updated_at: str = ""
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    body: str = ""
    type: str = "reference"
    path: str = ""
    links: list[str] = Field(default_factory=list)
    about_refs: list[dict] = Field(default_factory=list)


class Outcome(Record):
    outcome_id: str = Field(min_length=1)
    decision_ref: dict
    result: Literal["pass", "fail", "mixed", "unknown"]
    summary: str = Field(min_length=1)


RECORD_MODELS = {c.__name__: c for c in (Decision, FileChange, Commit, Memory, Outcome)}
