"""The hierarchy in a SQLite file, so nodes and layer rules can change while the system runs (decision A19).

`save` replaces the whole stored hierarchy in one transaction: a hierarchy has a handful of nodes, and replacing it
all keeps the file equal to what the aggregate holds. Nothing is ever partly saved.
"""
import sqlite3
from pathlib import Path

from .registry_csv import LAYER_COLUMNS, NODE_COLUMNS, hierarchy_from_rows, row_of_layer, row_of_node

SCHEMA = """
CREATE TABLE IF NOT EXISTS layers (
    layer_index     INTEGER PRIMARY KEY CHECK (layer_index >= 0),
    name            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT '',
    detail_level    TEXT,
    min_judge_score INTEGER CHECK (min_judge_score BETWEEN 1 AND 20),
    required_topics TEXT NOT NULL DEFAULT '',
    excluded_topics TEXT NOT NULL DEFAULT '',
    required_fields TEXT NOT NULL DEFAULT '',
    output_format   TEXT NOT NULL DEFAULT '',
    max_words       INTEGER CHECK (max_words >= 1),
    citation_level  TEXT
);
CREATE TABLE IF NOT EXISTS nodes (
    node_id           TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    layer_index       INTEGER NOT NULL CHECK (layer_index >= 0),
    parent_node_id    TEXT REFERENCES nodes(node_id),
    field_of_activity TEXT NOT NULL,
    is_terminal       INTEGER NOT NULL CHECK (is_terminal IN (0, 1)),
    reporting_format  TEXT,
    min_judge_score   INTEGER CHECK (min_judge_score BETWEEN 1 AND 20),
    confidentiality   TEXT NOT NULL
);
"""
LAYER_DB_COLUMNS = [c for c in LAYER_COLUMNS if c != "source"]


class SqliteHierarchyRepository:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")     # SQLite ignores foreign keys unless this is on for the connection
        self.db.executescript(SCHEMA)

    def is_empty(self):
        return self.db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0

    def load(self):
        layer_rows = [self._as_text(dict(zip(LAYER_DB_COLUMNS, r)))
                      for r in self.db.execute(f"SELECT {', '.join(LAYER_DB_COLUMNS)} FROM layers ORDER BY layer_index")]
        node_rows = [self._as_text(dict(zip(NODE_COLUMNS, r)), booleans=("is_terminal",))
                     for r in self.db.execute(f"SELECT {', '.join(NODE_COLUMNS)} FROM nodes ORDER BY rowid")]
        for row in node_rows:
            row["reporting_format"] = row["reporting_format"] or "none"
        return hierarchy_from_rows(node_rows, layer_rows)

    def save(self, hierarchy):
        with self.db:
            self._replace(hierarchy)

    def _replace(self, hierarchy):
        """Replace the hierarchy inside the caller's transaction."""
        hierarchy.check_complete()
        nodes = [hierarchy.root()] + hierarchy.descendants(hierarchy.root().node_id)    # parents before children
        self.db.execute("DELETE FROM nodes")
        self.db.execute("DELETE FROM layers")
        for layer in hierarchy.layers():
            if hierarchy.layer_definition(layer.index) is not None:
                self._insert("layers", LAYER_DB_COLUMNS, row_of_layer(layer))
        for node in nodes:
            self._insert("nodes", NODE_COLUMNS, row_of_node(node))

    def close(self):
        self.db.close()

    def _insert(self, table, columns, row):
        marks = ", ".join("?" * len(columns))
        self.db.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})",
                        [self._db_value(c, row[c]) for c in columns])

    @staticmethod
    def _db_value(column, text):
        """Text from a registry row to a database value. Columns that may be empty are stored as NULL."""
        if column == "is_terminal":
            return 1 if text == "true" else 0
        if column == "reporting_format":
            return None if text in ("", "none") else text
        if column in ("layer_index", "min_judge_score", "max_words"):
            return int(text) if text != "" else None
        if column in ("detail_level", "citation_level", "parent_node_id"):
            return text or None
        return text

    @staticmethod
    def _as_text(row, booleans=()):
        return {key: ("true" if value else "false") if key in booleans else ("" if value is None else str(value))
                for key, value in row.items()}
