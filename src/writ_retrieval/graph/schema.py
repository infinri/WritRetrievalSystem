"""Retrieval-only registries from Writ V1; see NOTICE.md for pinned source."""
from enum import Enum

class NodeType(str, Enum):
    """All node types in the graph. Retrievable subset per plan Section 2.3."""

    RULE = "Rule"
    ABSTRACTION = "Abstraction"
    CATEGORY = "Category"
    # Retrievable (participate in Stage 1-3 ranking)
    SKILL = "Skill"
    PLAYBOOK = "Playbook"
    TECHNIQUE = "Technique"
    ANTIPATTERN = "AntiPattern"
    FORBIDDEN_RESPONSE = "ForbiddenResponse"
    # Non-retrievable (bundle-expansion / template-only; Stage 4 surfacing only)
    PHASE = "Phase"
    RATIONALIZATION = "Rationalization"
    PRESSURE_SCENARIO = "PressureScenario"
    WORKED_EXAMPLE = "WorkedExample"
    SUBAGENT_ROLE = "SubagentRole"

NODE_ID_FIELDS = {'Rule': 'rule_id', 'Abstraction': 'abstraction_id', 'Category': 'category_id', 'Skill': 'skill_id', 'Playbook': 'playbook_id', 'Technique': 'technique_id', 'AntiPattern': 'antipattern_id', 'ForbiddenResponse': 'forbidden_id', 'Phase': 'phase_id', 'Rationalization': 'rationalization_id', 'PressureScenario': 'scenario_id', 'WorkedExample': 'example_id', 'SubagentRole': 'role_id'}
RANKED_METHODOLOGY_LABELS = ("Skill", "Playbook", "Technique", "AntiPattern", "ForbiddenResponse")
RETRIEVABLE_NODE_TYPES = frozenset({NodeType.RULE, NodeType.ABSTRACTION, *(NodeType(label) for label in RANKED_METHODOLOGY_LABELS)})
RECORD_ID_FIELDS = {'Memory': 'name', 'Decision': 'decision_id', 'FileChange': 'change_id', 'Commit': 'commit_hash', 'Project': 'name', 'FeedbackBatch': 'batch_id', 'TrustEvent': 'event_id', 'Document': 'doc_id', 'Chunk': 'chunk_id', 'OpenQuestion': 'question_id'}
RECORD_LABELS = frozenset(RECORD_ID_FIELDS)
