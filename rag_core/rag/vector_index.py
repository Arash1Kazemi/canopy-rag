"""The vector index (Phase 8A): the stored embedding of each chunk, and the exact search over them.

A VectorRecord is one chunk's vector plus what retrieval must know without opening the chunk: the chunk id, the item
and version it belongs to, its node, the embedding model that made the vector and the chunking policy that cut the
chunk. The model and the policy together are the index's IndexSignature: vectors of two models, or of two chunkings,
must never be compared, so a change of either means the index is rebuilt (rag/indexing.py).

H01 lives here as much as in the retriever: `rank` drops every record the IndexFilter does not admit BEFORE any score
is computed. A chunk of another node is never scored, so it cannot win, and it cannot push the node's own chunks out
of the top k either. Both adapters (infrastructure/memory.py and infrastructure/sqlite_vectors.py) call `rank`.

Exact search means every admitted vector is compared with the query. The case study has about a hundred chunks, so
this is fast enough, and it has no approximation error that could hide a retrieval bug (book Ch. 6).
"""
import math
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Protocol

from ..shared.kernel import DomainError


def cosine(a, b):
    """How much two vectors point the same way: 1 is the same direction, 0 is unrelated. A zero vector scores 0."""
    if len(a) != len(b):
        raise DomainError(f"cannot compare a vector of {len(a)} numbers with one of {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    length = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / length if length else 0.0


@dataclass(frozen=True)
class IndexSignature:
    """What made the vectors: the embedding model tag and the chunking policy name."""
    embedding_model: str
    chunking_policy: str

    def __post_init__(self):
        if not self.embedding_model.strip() or not self.chunking_policy.strip():
            raise DomainError("an index signature names an embedding model and a chunking policy")


@dataclass(frozen=True)
class VectorRecord:
    chunk_id: str
    item_id: str
    version_tag: str
    node_id: str
    embedding_model: str
    chunking_policy: str
    vector: tuple
    indexed_at: str = ""

    def __post_init__(self):
        if not self.vector:
            raise DomainError(f"chunk {self.chunk_id} has an empty vector")
        object.__setattr__(self, "vector", tuple(float(x) for x in self.vector))

    @property
    def signature(self):
        return IndexSignature(self.embedding_model, self.chunking_policy)


@dataclass(frozen=True)
class IndexFilter:
    """Which records a search may score: one node, and only the listed (item id, version tag) pairs.

    The retriever fills `versions` with the active version of each item of the node whose metadata matches the
    question's metadata filter, so node, active version and metadata are all applied here, before ranking."""
    node_id: str
    versions: frozenset

    def admits(self, record):
        return record.node_id == self.node_id and (record.item_id, record.version_tag) in self.versions


def rank(records: Iterable[VectorRecord], query_vector, k, index_filter: IndexFilter,
         similarity: Callable = cosine):
    """Filter first, then score, then keep the best k. Ties break on the chunk id, so the order is the same every run."""
    if k < 1:
        raise DomainError(f"k is at least 1, not {k}")
    admitted = [r for r in records if index_filter.admits(r)]          # H01: before any score is computed
    scored = [(similarity(query_vector, r.vector), r) for r in admitted]
    scored.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
    return [(record, score) for score, record in scored[:k]]


class VectorIndex(Protocol):
    def add(self, records: Iterable[VectorRecord]) -> None:
        """Store records. A record for a chunk id already stored replaces it."""

    def chunk_ids(self) -> set: ...

    def records(self, node_id: Optional[str] = None) -> list:
        """Every record, or the records of one node, ordered by chunk id."""

    def signatures(self) -> set:
        """The IndexSignatures of the stored records. An up-to-date index has one, an empty index none."""

    def clear(self) -> None:
        """Drop every record (a rebuild). Knowledge is untouched: a vector can always be made again (H04 is about versions)."""

    def search(self, query_vector, k: int, index_filter: IndexFilter) -> list:
        """(record, score) pairs, best first, at most k, only records the filter admits (H01)."""
