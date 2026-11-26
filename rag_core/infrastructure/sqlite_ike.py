"""IKE relations in a SQLite file (Phase 9), table `ike_relations`. By default the file is data/project.sqlite, next
to the hierarchy and the issues.

One row per edge. The UNIQUE constraint on (type, source, target) refuses a duplicate edge even if a caller skips the
domain rules; "similar" edges are stored with the smaller key first (the model does that), so the reverse is a
duplicate too. `add_all` stores a group in one transaction: all of it, or nothing.
"""
import sqlite3
from pathlib import Path

from ..ike.model import EntityRef, IkeRelation, sorted_relations

SCHEMA = """
CREATE TABLE IF NOT EXISTS ike_relations (
    relation_type TEXT NOT NULL,
    source_kind   TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    target_kind   TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    node_id       TEXT NOT NULL,
    evidence      TEXT NOT NULL DEFAULT '',
    basis         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    UNIQUE (relation_type, source_kind, source_id, target_kind, target_id)
);
CREATE INDEX IF NOT EXISTS ike_relations_node ON ike_relations (node_id);
"""
COLUMNS = ["relation_type", "source_kind", "source_id", "target_kind", "target_id", "node_id", "evidence", "basis",
           "created_at"]


def row_of_relation(r):
    return [r.relation_type.value, r.source.kind.value, r.source.key, r.target.kind.value, r.target.key,
            str(r.node_id), r.evidence, r.basis, r.created_at]


def relation_of_row(row):
    v = dict(zip(COLUMNS, row))
    return IkeRelation(relation_type=v["relation_type"], source=EntityRef(v["source_kind"], v["source_id"]),
                       target=EntityRef(v["target_kind"], v["target_id"]), node_id=v["node_id"],
                       created_at=v["created_at"], evidence=v["evidence"], basis=v["basis"])


class SqliteIkeRepository:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def add_all(self, relations):
        relations = list(relations)
        try:
            with self.db:                               # one transaction: commit at the end, roll back on any error
                self.db.executemany(f"INSERT INTO ike_relations ({', '.join(COLUMNS)}) "
                                    f"VALUES ({', '.join('?' * len(COLUMNS))})",
                                    [row_of_relation(r) for r in relations])
        except sqlite3.IntegrityError as error:
            raise ValueError(f"relation already stored or repeated, so nothing was saved: {error}") from error

    def all_relations(self):
        return sorted_relations(relation_of_row(r) for r in self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM ike_relations"))

    def relations_of_node(self, node_id):
        rows = self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM ike_relations WHERE node_id = ?", (str(node_id),))
        return sorted_relations(relation_of_row(r) for r in rows)

    def contains(self, relation):
        return self.db.execute(
            "SELECT 1 FROM ike_relations WHERE relation_type = ? AND source_kind = ? AND source_id = ? "
            "AND target_kind = ? AND target_id = ?", row_of_relation(relation)[:5]).fetchone() is not None

    def is_empty(self):
        return self.db.execute("SELECT COUNT(*) FROM ike_relations").fetchone()[0] == 0

    def close(self):
        self.db.close()
