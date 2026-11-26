"""Issue statuses and the moves allowed between them (proposal section 14.1, decision A30).

The proposal lists ten sample statuses. It does not say which moves are allowed, so the table below is a working
decision. The rule is simple: work goes forward (new, analyzing, the "identified" and "proposed" steps, in progress,
solved), a person may step back to analyzing when new facts appear, and archived is the end.
"""
from enum import Enum

from ..shared.kernel import DomainError


class IssueStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    KNOWLEDGE_IDENTIFIED = "knowledge_identified"
    EXECUTOR_IDENTIFIED = "executor_identified"
    SOLUTION_PROPOSED = "solution_proposed"
    IN_PROGRESS = "in_progress"
    AWAITING_DECISION = "awaiting_decision"
    SOLVED = "solved"
    UNSOLVED = "unsolved"
    ARCHIVED = "archived"


S = IssueStatus
ALLOWED_MOVES = {
    S.NEW: (S.ANALYZING, S.ARCHIVED),
    S.ANALYZING: (S.KNOWLEDGE_IDENTIFIED, S.EXECUTOR_IDENTIFIED, S.SOLUTION_PROPOSED, S.UNSOLVED, S.ARCHIVED),
    S.KNOWLEDGE_IDENTIFIED: (S.ANALYZING, S.EXECUTOR_IDENTIFIED, S.SOLUTION_PROPOSED, S.UNSOLVED, S.ARCHIVED),
    S.EXECUTOR_IDENTIFIED: (S.ANALYZING, S.KNOWLEDGE_IDENTIFIED, S.SOLUTION_PROPOSED, S.UNSOLVED, S.ARCHIVED),
    S.SOLUTION_PROPOSED: (S.ANALYZING, S.IN_PROGRESS, S.AWAITING_DECISION, S.UNSOLVED, S.ARCHIVED),
    S.IN_PROGRESS: (S.ANALYZING, S.AWAITING_DECISION, S.SOLVED, S.UNSOLVED),
    S.AWAITING_DECISION: (S.SOLUTION_PROPOSED, S.IN_PROGRESS, S.SOLVED, S.UNSOLVED),
    S.SOLVED: (S.ANALYZING, S.ARCHIVED),       # back to analyzing = reopened
    S.UNSOLVED: (S.ANALYZING, S.ARCHIVED),
    S.ARCHIVED: (),                            # the end: nothing moves out of archived
}

# The five values used in case_study/issues.csv before Phase 7. Each keeps its meaning; only the spelling changes.
LEGACY_STATUSES = {
    "new": S.NEW,
    "analyzing": S.ANALYZING,
    "in progress": S.IN_PROGRESS,
    "solved": S.SOLVED,
    "unsolved": S.UNSOLVED,
}


def parse_status(value):
    """An IssueStatus from its code value (in_progress) or a legacy value (in progress)."""
    if isinstance(value, IssueStatus):
        return value
    text = (value or "").strip().lower()
    if text in LEGACY_STATUSES:
        return LEGACY_STATUSES[text]
    try:
        return IssueStatus(text)
    except ValueError:
        allowed = ", ".join(s.value for s in IssueStatus)
        raise DomainError(f"H07: an issue status is one of {allowed}, not {value!r}") from None


def can_move(old, new):
    return parse_status(new) in ALLOWED_MOVES[parse_status(old)]


def check_move(old, new):
    old, new = parse_status(old), parse_status(new)
    if new not in ALLOWED_MOVES[old]:
        allowed = ", ".join(s.value for s in ALLOWED_MOVES[old]) or "nothing (it is the end)"
        raise DomainError(f"H07: an issue cannot move from {old.value} to {new.value}; from {old.value} it can move to {allowed}")
    return new
