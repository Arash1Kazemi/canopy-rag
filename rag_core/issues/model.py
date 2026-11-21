"""Issue and sub-issue model (Phase 7): issue identification, metadata, hierarchy relationships, and comparison logic."""
import re
from dataclasses import dataclass, field
from typing import Optional

from ..shared.kernel import DomainError, parse_enum
from ..organization.model import NodeIdentifier

ISSUE_ID_PATTERN = re.compile(r"I\d+")
VALID_STATUSES = ("new", "analyzing", "in_progress", "solved", "unsolved")


@dataclass(frozen=True)
class IssueIdentifier:
    """The stable identifier of an issue, such as I01."""
    value: str

    def __post_init__(self):
        if not ISSUE_ID_PATTERN.fullmatch(self.value or ""):
            raise DomainError(f"an issue id starts with 'I' followed by digits, not {self.value!r}")

    def __str__(self):
        return self.value


@dataclass(frozen=True)
class Issue:
    """An organizational issue or sub-issue (Phase 7)."""
    issue_id: IssueIdentifier
    node_id: NodeIdentifier
    title: str
    description: str
    status: str = "new"
    parent_issue_id: Optional[IssueIdentifier] = None

    def __post_init__(self):
        if not self.title.strip():
            raise DomainError(f"issue {self.issue_id} needs a non-empty title")
        if not self.description.strip():
            raise DomainError(f"issue {self.issue_id} needs a non-empty description")
        if self.status not in VALID_STATUSES:
            raise DomainError(f"issue {self.issue_id}: status must be one of {VALID_STATUSES}, not {self.status!r}")


class IssueManager:
    """Manages issues, sub-issue relationships, and issue comparison logic."""

    def __init__(self):
        self._issues = {}  # IssueIdentifier -> Issue

    def add_issue(self, issue: Issue):
        if issue.issue_id in self._issues:
            raise DomainError(f"issue {issue.issue_id} already exists")
        if issue.parent_issue_id is not None and issue.parent_issue_id not in self._issues:
            raise DomainError(f"parent issue {issue.parent_issue_id} does not exist for sub-issue {issue.issue_id}")
        self._issues[issue.issue_id] = issue

    def get_issue(self, issue_id: IssueIdentifier) -> Optional[Issue]:
        return self._issues.get(issue_id)

    def all_issues(self) -> tuple:
        return tuple(self._issues.values())

    def sub_issues(self, parent_id: IssueIdentifier) -> tuple:
        """Return all direct sub-issues of the given parent issue."""
        return tuple(i for i in self._issues.values() if i.parent_issue_id == parent_id)

    def compare_issues(self, issue_a_id: IssueIdentifier, issue_b_id: IssueIdentifier) -> float:
        """Compare two issues for text similarity and overlap based on title and description keywords."""
        a = self._issues.get(issue_a_id)
        b = self._issues.get(issue_b_id)
        if not a or not b:
            raise DomainError("cannot compare non-existent issues")
        
        words_a = set(re.findall(r"\w+", (a.title + " " + a.description).lower()))
        words_b = set(re.findall(r"\w+", (b.title + " " + b.description).lower()))
        
        if not words_a or not words_b:
            return 0.0
        
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union)
        return round(jaccard, 2)
