"""Load issues from case_study/issues.csv into an IssueManager."""
import csv
from pathlib import Path

from ..organization.model import NodeIdentifier
from .model import Issue, IssueIdentifier, IssueManager


class CsvIssueRepository:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> IssueManager:
        manager = IssueManager()
        if not self.path.exists():
            return manager
        with open(self.path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                issue_id = IssueIdentifier(row["issue_id"].strip())
                node_id = NodeIdentifier(row["node_id"].strip())
                parent_id = IssueIdentifier(row["parent_issue_id"].strip()) if row.get("parent_issue_id", "").strip() else None
                title = row["title"].strip()
                description = row["description"].strip()
                status = row.get("status", "new").strip().replace(" ", "_") or "new"
                issue = Issue(
                    issue_id=issue_id,
                    node_id=node_id,
                    title=title,
                    description=description,
                    status=status,
                    parent_issue_id=parent_id,
                )
                manager.add_issue(issue)
        return manager
