"""The Issue entity (proposal sections 12.1 and 12.2).

A sub-issue is an Issue with a parent: it has the same fields, its own id, status and progress (12.2). An Issue is
frozen. A change makes a new Issue through a method that checks the rule (for example `with_status`), and the
repository stores it.

Rules that look at one issue live here. Rules that look at several issues (a sub-issue is in its parent's node, no
cycles) live in `rules.py`, because one issue cannot see the others.
"""
import re
from dataclasses import dataclass, replace
from typing import Optional

from ..organization.model import NodeIdentifier
from ..shared.kernel import DomainError
from .status import IssueStatus, check_move, parse_status

ISSUE_ID_PATTERN = re.compile(r"I\d+")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}([T ][0-9:.]+Z?)?")

# The five kinds of issue the glossary names (one Issue class with a type field, glossary "Decisions to confirm").
ISSUE_TYPES = ("problem", "question", "need", "research_gap", "operational_concern")
# The proposal gives no priority scale (12.1 says the system suggests one). Decision A32: three levels and "not set".
PRIORITIES = ("not_set", "low", "medium", "high")


@dataclass(frozen=True)
class IssueIdentifier:
    """The stable identifier of an issue, such as I01."""
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or not ISSUE_ID_PATTERN.fullmatch(self.value):
            raise DomainError(f"an issue id starts with 'I' followed by digits, not {self.value!r}")

    @property
    def number(self):
        return int(self.value[1:])

    def __str__(self):
        return self.value


def as_issue_id(value):
    return value if isinstance(value, IssueIdentifier) else IssueIdentifier(str(value).strip())


@dataclass(frozen=True, kw_only=True)
class Issue:
    """An organizational issue or sub-issue. All fields are named when an Issue is made.

    metadata is the free metadata map (12.1); it is stored as sorted (key, value) pairs so two equal maps give equal
    issues. knowledge_ids, executor_ids, proposed_solution, research_completed and review_approved are the facts the
    progress rules read (14.1); Phases 8 and 9 fill knowledge and executors through the IKE model.
    """
    issue_id: IssueIdentifier
    node_id: NodeIdentifier
    title: str
    description: str
    created_at: str
    field_of_activity: str
    status: IssueStatus = IssueStatus.NEW
    parent_issue_id: Optional[IssueIdentifier] = None
    issue_type: str = "problem"
    priority: str = "not_set"
    category: str = ""
    position: int = 1
    blocked_by: tuple = ()
    metadata: tuple = ()
    knowledge_ids: tuple = ()
    executor_ids: tuple = ()
    proposed_solution: str = ""
    research_completed: bool = False
    review_approved: bool = False

    def __post_init__(self):
        set_ = lambda name, value: object.__setattr__(self, name, value)
        set_("issue_id", as_issue_id(self.issue_id))
        if not isinstance(self.node_id, NodeIdentifier):
            set_("node_id", NodeIdentifier(str(self.node_id)))
        if self.parent_issue_id is not None:
            set_("parent_issue_id", as_issue_id(self.parent_issue_id))
        set_("status", parse_status(self.status))
        set_("blocked_by", tuple(as_issue_id(b) for b in self.blocked_by))
        metadata = dict(self.metadata)
        set_("metadata", tuple(sorted((str(k).strip(), str(v).strip()) for k, v in metadata.items())))
        set_("knowledge_ids", tuple(str(k) for k in self.knowledge_ids))
        set_("executor_ids", tuple(str(e) for e in self.executor_ids))
        me = self.issue_id
        for name in ("title", "description", "field_of_activity"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise DomainError(f"issue {me} needs a non-empty {name.replace('_', ' ')}")
        if not isinstance(self.created_at, str) or not DATE_PATTERN.fullmatch(self.created_at):
            raise DomainError(f"issue {me}: created_at is a date such as 2026-11-25 or 2026-11-25T10:00:00Z, not {self.created_at!r}")
        if self.issue_type not in ISSUE_TYPES:
            raise DomainError(f"issue {me}: issue_type must be one of {', '.join(ISSUE_TYPES)}, not {self.issue_type!r}")
        if self.priority not in PRIORITIES:
            raise DomainError(f"issue {me}: priority must be one of {', '.join(PRIORITIES)}, not {self.priority!r}")
        if not isinstance(self.position, int) or isinstance(self.position, bool) or self.position < 1:
            raise DomainError(f"issue {me}: position among its siblings is a whole number from 1, not {self.position!r}")
        if self.parent_issue_id == me:
            raise DomainError(f"issue {me} cannot be its own parent")
        if me in self.blocked_by:
            raise DomainError(f"issue {me} cannot be blocked by itself")
        if len(set(self.blocked_by)) != len(self.blocked_by):
            raise DomainError(f"issue {me} lists the same blocking issue twice")
        if any(not k for k, _ in self.metadata):
            raise DomainError(f"issue {me}: a metadata key cannot be empty")

    @property
    def is_sub_issue(self):
        return self.parent_issue_id is not None

    @property
    def meta(self):
        """The free metadata map as a dict (a copy)."""
        return dict(self.metadata)

    def with_status(self, new_status):
        """H07: only the moves in status.ALLOWED_MOVES are possible."""
        return replace(self, status=check_move(self.status, new_status))

    def with_blocker(self, blocker_id):
        blocker_id = as_issue_id(blocker_id)
        if blocker_id in self.blocked_by:
            raise DomainError(f"issue {self.issue_id} is already blocked by {blocker_id}")
        return replace(self, blocked_by=self.blocked_by + (blocker_id,))

    def with_changes(self, **changes):
        """A copy with other facts, such as a proposed solution. The status changes only through with_status."""
        if "status" in changes or "issue_id" in changes:
            raise DomainError("the id never changes, and the status changes only through with_status (H07)")
        return replace(self, **changes)
