"""Record-aware graph identity, deliberately separate from doctrine candidate types."""
from dataclasses import dataclass
import json
from .schema import NODE_ID_FIELDS, RECORD_ID_FIELDS

GRAPH_ID_FIELDS = {**NODE_ID_FIELDS, **RECORD_ID_FIELDS,
                   "Outcome": "outcome_id", "FeedbackObservation": "observation_id",
                   "RecordRevision": "revision_id", "ReviewSnapshot": "review_id"}


@dataclass(frozen=True, order=True)
class Key:
    project: str
    label: str
    id: str

    @property
    def token(self):
        return "@" + json.dumps([self.project, self.label, self.id], separators=(",", ":"), ensure_ascii=True)

    def as_dict(self):
        return {"project": self.project, "label": self.label, "id": self.id}

    @classmethod
    def of(cls, label, props):
        ident = props.get(GRAPH_ID_FIELDS.get(label, ""))
        if not isinstance(ident, str) or not ident:
            raise ValueError(f"missing canonical identity for {label}")
        project = props.get("project", "writ" if label in NODE_ID_FIELDS else "") or ""
        return cls(project, label, ident)

    @classmethod
    def parse(cls, ref):
        if not isinstance(ref, dict) or set(ref) != {"project", "label", "id"}:
            raise ValueError("references require exactly project, label, id")
        if ref["label"] not in GRAPH_ID_FIELDS or any(not isinstance(v, str) or not v or "\x00" in v for v in ref.values()):
            raise ValueError("invalid graph reference")
        return cls(ref["project"], ref["label"], ref["id"])
