"""Issues in a SQLite file (Phase 7). By default the file is data/project.sqlite, next to the hierarchy (decision A36).

`add_all` stores a group of issues in one transaction: if one row fails, none is kept. That is how accepted
sub-issue suggestions are saved together (decision A35). Lists and the metadata map are stored as JSON text.
"""
import json
import sqlite3
from pathlib import Path

from ..issues.model import Issue

SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    issue_id           TEXT PRIMARY KEY,
    node_id            TEXT NOT NULL,
    parent_issue_id    TEXT REFERENCES issues(issue_id),
    title              TEXT NOT NULL,
    description        TEXT NOT NULL,
    status             TEXT NOT NULL,
    issue_type         TEXT NOT NULL,
    field_of_activity  TEXT NOT NULL,
    priority           TEXT NOT NULL,
    category           TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL,
    position           INTEGER NOT NULL CHECK (position >= 1),
    blocked_by         TEXT NOT NULL DEFAULT '[]',
    metadata           TEXT NOT NULL DEFAULT '{}',
    knowledge_ids      TEXT NOT NULL DEFAULT '[]',
    executor_ids       TEXT NOT NULL DEFAULT '[]',
    proposed_solution  TEXT NOT NULL DEFAULT '',
    research_completed INTEGER NOT NULL DEFAULT 0 CHECK (research_completed IN (0, 1)),
    review_approved    INTEGER NOT NULL DEFAULT 0 CHECK (review_approved IN (0, 1))
);
CREATE TABLE IF NOT EXISTS issue_imports (
    source      TEXT PRIMARY KEY,
    imported_at TEXT NOT NULL
);
"""
COLUMNS = ["issue_id", "node_id", "parent_issue_id", "title", "description", "status", "issue_type", "field_of_activity",
           "priority", "category", "created_at", "position", "blocked_by", "metadata", "knowledge_ids", "executor_ids",
           "proposed_solution", "research_completed", "review_approved"]
JSON_LISTS = ("blocked_by", "knowledge_ids", "executor_ids")
FLAGS = ("research_completed", "review_approved")


def row_of_issue(issue):
    row = {
        "issue_id": str(issue.issue_id), "node_id": str(issue.node_id),
        "parent_issue_id": str(issue.parent_issue_id) if issue.parent_issue_id else None,
        "title": issue.title, "description": issue.description, "status": issue.status.value,
        "issue_type": issue.issue_type, "field_of_activity": issue.field_of_activity, "priority": issue.priority,
        "category": issue.category, "created_at": issue.created_at, "position": issue.position,
        "metadata": json.dumps(dict(issue.metadata), sort_keys=True, ensure_ascii=False),
        "proposed_solution": issue.proposed_solution,
    }
    for name in JSON_LISTS:
        row[name] = json.dumps([str(x) for x in getattr(issue, name)])
    for name in FLAGS:
        row[name] = 1 if getattr(issue, name) else 0
    return row


def issue_of_row(row):
    values = dict(row)
    for name in JSON_LISTS:
        values[name] = tuple(json.loads(values[name]))
    for name in FLAGS:
        values[name] = bool(values[name])
    values["metadata"] = json.loads(values["metadata"])
    return Issue(**values)


def parents_first(issues):
    """Order a group so that a parent in the group comes before its sub-issues (the foreign key needs it). A group that
    is already in a good order keeps its order."""
    by_id = {i.issue_id: i for i in issues}
    ordered, placed, visiting = [], set(), set()

    def place(issue):
        if issue.issue_id in placed or issue.issue_id in visiting:
            return                                # placed already, or a cycle: let the database refuse it
        visiting.add(issue.issue_id)
        if issue.parent_issue_id in by_id:
            place(by_id[issue.parent_issue_id])
        placed.add(issue.issue_id)
        ordered.append(issue)
    for issue in issues:
        place(issue)
    return ordered


class SqliteIssueRepository:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    def get(self, issue_id):
        found = self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM issues WHERE issue_id = ?", (str(issue_id),)).fetchone()
        return None if found is None else issue_of_row(zip(COLUMNS, found))

    def all_issues(self):
        return [issue_of_row(zip(COLUMNS, r)) for r in self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM issues ORDER BY rowid")]

    def is_empty(self):
        return self.db.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 0

    def add_all(self, issues):
        issues = list(issues)
        _refuse_repeats(issues, lambda i: self.get(i.issue_id) is not None)
        try:
            with self.db:                                # one transaction: commit at the end, roll back on any error
                for issue in parents_first(issues):
                    self._insert(row_of_issue(issue))
        except sqlite3.Error as error:
            raise ValueError(f"the database refused the group, so nothing was saved: {error}") from error

    def update(self, issue):
        if self.get(issue.issue_id) is None:
            raise ValueError(f"issue {issue.issue_id} is not stored, so it cannot be updated")
        row = row_of_issue(issue)
        with self.db:
            self.db.execute(f"UPDATE issues SET {', '.join(f'{c} = ?' for c in COLUMNS[1:])} WHERE issue_id = ?",
                            [row[c] for c in COLUMNS[1:]] + [row["issue_id"]])

    def was_imported(self, source):
        return self.db.execute("SELECT 1 FROM issue_imports WHERE source = ?", (source,)).fetchone() is not None

    def import_once(self, source, issues, imported_at):
        """Add the seed issues and remember the source, in one transaction. A second import of the same source does nothing."""
        if self.was_imported(source):
            return False
        issues = list(issues)
        _refuse_repeats(issues, lambda i: self.get(i.issue_id) is not None)
        with self.db:
            for issue in parents_first(issues):
                self._insert(row_of_issue(issue))
            self.db.execute("INSERT INTO issue_imports VALUES (?, ?)", (source, imported_at))
        return True

    def seed_rows(self, table="case_study_issues"):
        """The rows of the seed table that project_db.migrate wrote into this file, or None when it is not there."""
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is None:
            return None
        cursor = self.db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, r)) for r in cursor]

    def close(self):
        self.db.close()

    def _insert(self, row):
        self.db.execute(f"INSERT INTO issues ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                        [row[c] for c in COLUMNS])


def _refuse_repeats(issues, is_stored):
    ids = [i.issue_id for i in issues]
    if len(set(ids)) != len(ids):
        raise ValueError("the same issue id appears twice in one group")
    stored = [str(i.issue_id) for i in issues if is_stored(i)]
    if stored:
        raise ValueError(f"issue id already stored: {', '.join(stored)}")

