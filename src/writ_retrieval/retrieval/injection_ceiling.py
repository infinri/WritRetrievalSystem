"""Writ V1 fenced text clamps (extracted subset)."""
from writ_retrieval.shared.injection_text import is_fence_close
TRUNCATION_MARKER = "[Writ: section truncated at the character ceiling]"

def clamp_lines(text: str, limit: int) -> str:
    """Whole lines of `text` that fit `limit`, plus the truncation marker when cut."""
    if len(text) <= limit:
        return text
    if limit <= len(TRUNCATION_MARKER):
        return ""
    room = limit - len(TRUNCATION_MARKER) - 1
    kept: list[str] = []
    used = 0
    for line in text.split("\n"):
        cost = len(line) + (1 if kept else 0)
        if used + cost > room:
            break
        kept.append(line)
        used += cost
    kept.append(TRUNCATION_MARKER)
    return "\n".join(kept)

def clamp_fenced(text: str, limit: int) -> str:
    """clamp_lines for a fenced block: a cut block keeps its close line, with the truncation
    marker inside it. Text whose last line is not a fence close is clamped by clamp_lines."""
    if len(text) <= limit:
        return text
    head, _, close = text.rpartition("\n")
    if not head or not is_fence_close(close):
        return clamp_lines(text, limit)
    cut = clamp_lines(head, limit - len(close) - 1)
    if cut in ("", TRUNCATION_MARKER):
        return ""
    return f"{cut}\n{close}"
