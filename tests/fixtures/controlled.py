"""Synthetic mechanics fixture; this encoder is NOT a semantic-search model."""
import numpy as np

TOKENS = ("sql", "parameterized", "database", "async", "blocking", "python", "plan", "approval", "cat", "unrelated")


class ControlledEncoder:
    def __init__(self):
        self.batches = 0

    def encode(self, text):
        if isinstance(text, list):
            self.batches += 1
            return np.array([self.encode(item) for item in text])
        result = np.zeros(384, dtype=np.float32)
        for index, token in enumerate(TOKENS):
            result[index] = text.lower().split().count(token)
        if not result.any():
            result[-1] = 1
        return result / np.linalg.norm(result)

    def encode_batch(self, texts):
        self.batches += 1
        return [self.encode(text).tolist() for text in texts]


NODES = [
    ("Rule", {"rule_id": "SQL-001", "trigger": "sql database", "statement": "Use parameterized sql", "domain": "database", "severity": "critical", "confidence": "production-validated", "authority": "human", "project": "writ", "provenance": "hand-authored", "source_origin": "ingest", "last_verified": "2000-01-01", "deliberate": True}),
    ("Rule", {"rule_id": "ASYNC-001", "trigger": "async python", "statement": "Avoid blocking async", "domain": "python", "severity": "high", "project": "writ", "authority": "ai-provisional"}),
    ("Rule", {"rule_id": "PLAN-001", "trigger": "plan approval", "statement": "Require approval plan", "domain": "process", "project": "writ"}),
    ("Rule", {"rule_id": "MANDATORY-001", "trigger": "sql", "statement": "sql", "mandatory": True}),
    ("Rule", {"rule_id": "OLD-001", "trigger": "sql", "statement": "sql", "superseded": True}),
    ("ForbiddenResponse", {"forbidden_id": "FRB-001", "trigger": "cat", "statement": "cat", "forbidden_phrases": '["cat unrelated"]', "what_to_say_instead": "plan", "domain": "communication", "project": "writ"}),
    ("Skill", {"skill_id": "SKL-001", "trigger": "plan", "statement": "approval", "domain": "process", "project": "writ"}),
    ("Category", {"category_id": "CAT-001", "routes": ["semantic"]}),
    ("Abstraction", {"abstraction_id": "ABS-001", "summary": "database sql", "rule_count": 2}),
]
EDGES = [("SQL-001", "RELATED_TO", "ASYNC-001"), ("SQL-001", "BELONGS_TO", "CAT-001"), ("ABS-001", "ABSTRACTS", "SQL-001")]
QUERIES = [
    {"query_text": "sql database", "project": "app", "budget_tokens": 2000},
    {"query_text": "async blocking", "project": "app", "budget_tokens": 600},
    {"query_text": "plan approval", "retrieval_mode": "literal", "budget_tokens": 1000},
    {"query_text": "cat", "node_types": ["ForbiddenResponse"], "budget_tokens": 150},
    {"query_text": "sql", "exclude_rule_ids": ["SQL-001"], "budget_tokens": 2000},
    {"query_text": "unrelated", "budget_tokens": 2000},
    {"query_text": "sql", "budget_tokens": 10},
]
