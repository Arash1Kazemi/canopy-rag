"""Executors in a SQLite file (Phase 9). By default the file is data/project.sqlite, next to the hierarchy and issues.

`add_all` stores a group in one transaction: if one row fails, none is kept. Lists are stored as JSON text.
"""
import json
import sqlite3
from pathlib import Path

from ..executors.model import Executor

SCHEMA = """
CREATE TABLE IF NOT EXISTS executors (
    executor_id       TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    node_id           TEXT NOT NULL,
    kind              TEXT NOT NULL,
    role              TEXT NOT NULL DEFAULT '',
    expertise         TEXT NOT NULL DEFAULT '[]',
    past_projects     TEXT NOT NULL DEFAULT '[]',
    documents_written TEXT NOT NULL DEFAULT '[]',
    availability      TEXT NOT NULL DEFAULT ''
);
"""
COLUMNS = ["executor_id", "name", "node_id", "kind", "role", "expertise", "past_projects", "documents_written", "availability"]


def row_of_executor(executor):
    return {
        "executor_id": str(executor.executor_id), "name": executor.name, "node_id": str(executor.node_id),
        "kind": executor.kind, "role": executor.role,
        "expertise": json.dumps(list(executor.expertise), ensure_ascii=False),
        "past_projects": json.dumps(list(executor.past_projects), ensure_ascii=False),
        "documents_written": json.dumps([[d.doc_id, d.title] for d in executor.documents_written], ensure_ascii=False),
        "availability": executor.availability,
    }


def executor_of_row(row):
    values = dict(row)
    values["expertise"] = tuple(json.loads(values["expertise"]))
    values["past_projects"] = tuple(json.loads(values["past_projects"]))
    values["documents_written"] = tuple(tuple(d) for d in json.loads(values["documents_written"]))
    return Executor(**values)


class SqliteExecutorRepository:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def get(self, executor_id):
        found = self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM executors WHERE executor_id = ?", (str(executor_id),)).fetchone()
        return None if found is None else executor_of_row(zip(COLUMNS, found))

    def all_executors(self):
        return [executor_of_row(zip(COLUMNS, r)) for r in self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM executors ORDER BY rowid")]

    def is_empty(self):
        return self.db.execute("SELECT COUNT(*) FROM executors").fetchone()[0] == 0

    def add_all(self, executors):
        executors = list(executors)
        ids = [str(e.executor_id) for e in executors]
        if len(set(ids)) != len(ids):
            raise ValueError("the same executor id appears twice in one group")
        stored = [i for i in ids if self.get(i) is not None]
        if stored:
            raise ValueError(f"executor id already stored: {', '.join(stored)}")
        try:
            with self.db:                                # one transaction: commit at the end, roll back on any error
                for executor in executors:
                    row = row_of_executor(executor)
                    self.db.execute(f"INSERT INTO executors ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                                    [row[c] for c in COLUMNS])
        except sqlite3.Error as error:
            raise ValueError(f"the database refused the group, so nothing was saved: {error}") from error

    def update(self, executor):
        if self.get(executor.executor_id) is None:
            raise ValueError(f"executor {executor.executor_id} is not stored, so it cannot be updated")
        row = row_of_executor(executor)
        with self.db:
            self.db.execute(f"UPDATE executors SET {', '.join(f'{c} = ?' for c in COLUMNS[1:])} WHERE executor_id = ?",
                            [row[c] for c in COLUMNS[1:]] + [row["executor_id"]])

    def close(self):
        self.db.close()
