"""A SQLite knowledge repository: the local database the proposal asks for (sections 9.3 and 17).

SQLite comes with Python, so nothing has to be installed. Versions are only ever inserted, never updated or
deleted (H04). The active tag is the one value that changes.
"""
import json
import sqlite3
from pathlib import Path

from ..knowledge.metadata import MetadataRecord
from ..knowledge.model import KnowledgeChunk, KnowledgeItem, KnowledgeItemId, KnowledgeVersion, SourceLocation, VersionTag

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id     TEXT PRIMARY KEY,
    node_id     TEXT NOT NULL,
    active_tag  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    item_id       TEXT NOT NULL REFERENCES items(item_id),
    tag           TEXT NOT NULL,
    sequence      INTEGER NOT NULL,
    previous_tag  TEXT,
    diff_summary  TEXT NOT NULL DEFAULT '',
    text          TEXT NOT NULL,
    text_sha256   TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (item_id, tag)
);
CREATE INDEX IF NOT EXISTS versions_by_text ON versions(text_sha256);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     TEXT PRIMARY KEY,
    item_id      TEXT NOT NULL,
    tag          TEXT NOT NULL,
    node_id      TEXT NOT NULL,
    ord          INTEGER NOT NULL,
    text         TEXT NOT NULL,
    source_file  TEXT NOT NULL,
    char_start   INTEGER NOT NULL,
    char_end     INTEGER NOT NULL,
    page_start   INTEGER,
    page_end     INTEGER,
    heading_path TEXT NOT NULL,
    FOREIGN KEY (item_id, tag) REFERENCES versions(item_id, tag)
);
CREATE INDEX IF NOT EXISTS chunks_by_node ON chunks(node_id);
CREATE TRIGGER IF NOT EXISTS versions_never_change BEFORE UPDATE ON versions
BEGIN SELECT RAISE(ABORT, 'H04: a stored version is never changed'); END;
CREATE TRIGGER IF NOT EXISTS versions_never_deleted BEFORE DELETE ON versions
BEGIN SELECT RAISE(ABORT, 'H04: a stored version is never deleted'); END;
"""
HEADING_SEP = " > "


class SqliteKnowledgeRepository:
    def __init__(self, path=":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    # --- writing
    def save(self, item):
        with self.db:  # one transaction: all of the item, or nothing
            self.db.execute("INSERT INTO items(item_id, node_id, active_tag) VALUES (?, ?, ?) "
                            "ON CONFLICT(item_id) DO UPDATE SET active_tag = excluded.active_tag",
                            (str(item.item_id), item.node_id, str(item.active_tag)))
            stored = {row[0] for row in self.db.execute("SELECT tag FROM versions WHERE item_id = ?", (str(item.item_id),))}
            missing = stored - {str(v.tag) for v in item.versions}
            if missing:
                raise ValueError(f"H04: versions {sorted(missing)} of {item.item_id} cannot be removed")
            for v in item.versions:
                if str(v.tag) in stored:
                    continue
                self.db.execute("INSERT INTO versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (str(item.item_id), str(v.tag), v.sequence, None if v.previous_tag is None else str(v.previous_tag),
                                 v.diff_summary, v.text, v.metadata["text_sha256"], json.dumps(v.metadata.as_dict(), sort_keys=True)))
                self.db.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                    (c.chunk_id, str(item.item_id), str(v.tag), c.node_id, c.order, c.text, c.location.source_file,
                     c.location.char_start, c.location.char_end, c.location.page_start, c.location.page_end,
                     HEADING_SEP.join(c.location.heading_path)) for c in v.chunks])

    # --- reading
    def _chunks(self, item_id, tag):
        rows = self.db.execute("SELECT chunk_id, node_id, ord, text, source_file, char_start, char_end, page_start, page_end, "
                               "heading_path FROM chunks WHERE item_id = ? AND tag = ? ORDER BY ord", (item_id, tag))
        iid, vtag = KnowledgeItemId(item_id), VersionTag(tag)
        return tuple(KnowledgeChunk(cid, node, order, text,
                                    SourceLocation(iid, vtag, src, a, b, ps, pe, tuple(h.split(HEADING_SEP)) if h else ()))
                     for cid, node, order, text, src, a, b, ps, pe, h in rows)

    def get(self, item_id):
        row = self.db.execute("SELECT node_id, active_tag FROM items WHERE item_id = ?", (str(item_id),)).fetchone()
        if row is None:
            return None
        versions = [KnowledgeVersion(VersionTag(tag), text, MetadataRecord(json.loads(meta)), self._chunks(str(item_id), tag),
                                     sequence=seq, previous_tag=VersionTag(prev) if prev else None, diff_summary=diff)
                    for tag, seq, prev, diff, text, meta in self.db.execute(
                        "SELECT tag, sequence, previous_tag, diff_summary, text, metadata_json FROM versions "
                        "WHERE item_id = ? ORDER BY sequence", (str(item_id),))]
        return KnowledgeItem(str(item_id), row[0], versions, VersionTag(row[1]))

    def all_items(self):
        return [self.get(r[0]) for r in self.db.execute("SELECT item_id FROM items ORDER BY rowid")]

    def items_of_node(self, node_id):
        return [self.get(r[0]) for r in self.db.execute("SELECT item_id FROM items WHERE node_id = ? ORDER BY rowid", (str(node_id),))]

    def find_by_text(self, text_hash):
        rows = self.db.execute("SELECT item_id, tag FROM versions WHERE text_sha256 = ? ORDER BY item_id, sequence", (str(text_hash),))
        pairs = []
        for item_id, tag in rows.fetchall():
            item = self.get(item_id)
            pairs.append((item, item.version(tag)))
        return pairs

    def active_chunks(self, node_id=None):
        sql = ("SELECT c.item_id, c.tag FROM items i JOIN chunks c ON c.item_id = i.item_id AND c.tag = i.active_tag "
               + ("WHERE i.node_id = ? " if node_id is not None else "") + "GROUP BY c.item_id, c.tag ORDER BY i.rowid")
        args = (str(node_id),) if node_id is not None else ()
        return [c for item_id, tag in self.db.execute(sql, args).fetchall() for c in self._chunks(item_id, tag)]
