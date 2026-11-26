"""The IssueRepository interface. The adapters are in infrastructure/: InMemoryIssueRepository (memory.py) and
SqliteIssueRepository (sqlite_issues.py). The seed CSV is imported by infrastructure/issues_csv.py.

Both adapters pass the same contract tests (tests/test_core_issue_storage.py).
"""
from typing import Optional, Protocol


class IssueRepository(Protocol):
    def get(self, issue_id) -> Optional[object]:
        """The issue, or None."""

    def all_issues(self) -> list:
        """Every stored issue, in the order they were first added."""

    def add_all(self, issues) -> None:
        """Add new issues in one transaction: all of them are stored, or none. A known id is refused."""

    def update(self, issue) -> None:
        """Replace a stored issue with a changed copy. An unknown id is refused."""

    def is_empty(self) -> bool:
        """True when no issue is stored."""
