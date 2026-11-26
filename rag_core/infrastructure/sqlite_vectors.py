"""The vector index in SQLite (Phase 8A). It can share a file with the knowledge repository (its table is `chunk_vectors`).

A vector is stored as a blob of 8-byte floats (the standard `array` module), so it comes back exactly as it went in.
Search reads the node's rows only (the WHERE clause), then rag/vector_index.rank drops the inactive versions and
scores what is left, so a foreign-node chunk is never even loaded (H01). The index is exact: it compares the question
with every admitted vector, which is fine for a corpus of this size.
"""
import sqlite3
from array import array
from pathlib import Path

from ..rag.vector_index import IndexSignature, VectorRecord, cosine, rank

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunk_vectors (
    chunk_id        TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL,
    version_tag     TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    chunking_policy TEXT NOT NULL,
    dims            INTEGER NOT NULL,
    vector          BLOB NOT NULL,
    indexed_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chunk_vectors_by_node ON chunk_vectors(node_id);
"""
COLUMNS = "chunk_id, item_id, version_tag, node_id, embedding_model, chunking_policy, dims, vector, indexed_at"


def _blob(vector):
    return array("d", vector).tobytes()


def _vector(blob, dims):
    values = array("d")
    values.frombytes(blob)
    if len(values) != dims:
        raise ValueError(f"a stored vector has {len(values)} numbers, but its row says {dims}")
    return tuple(values)


class SqliteVectorIndex:
    def __init__(self, path=":memory:", similarity=cosine):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)
        self.similarity = similarity

    def close(self):
        self.db.close()

    def add(self, records):
        rows = [(r.chunk_id, r.item_id, r.version_tag, r.node_id, r.embedding_model, r.chunking_policy,
                 len(r.vector), _blob(r.vector), r.indexed_at) for r in records]
        with self.db:   # one batch, one transaction
            self.db.executemany(f"INSERT OR REPLACE INTO chunk_vectors({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    def chunk_ids(self):
        return {row[0] for row in self.db.execute("SELECT chunk_id FROM chunk_vectors")}

    def records(self, node_id=None):
        sql = f"SELECT {COLUMNS} FROM chunk_vectors " + ("WHERE node_id = ? " if node_id is not None else "") + "ORDER BY chunk_id"
        rows = self.db.execute(sql, (str(node_id),) if node_id is not None else ())
        return [VectorRecord(cid, item, tag, node, model, policy, _vector(blob, dims), at)
                for cid, item, tag, node, model, policy, dims, blob, at in rows]

    def signatures(self):
        return {IndexSignature(m, p) for m, p in self.db.execute("SELECT DISTINCT embedding_model, chunking_policy FROM chunk_vectors")}

    def clear(self):
        with self.db:
            self.db.execute("DELETE FROM chunk_vectors")

    def search(self, query_vector, k, index_filter):
        return rank(self.records(index_filter.node_id), query_vector, k, index_filter, self.similarity)
