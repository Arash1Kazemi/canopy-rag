"""The retrieval use case (Phase 8B): the k chunks of the asking node that are closest to a question.

The order of the steps is the point (H01, proposal 8.1 steps 3 to 6 and 8.4 "respects the node boundaries"):
1. Validate the node through the node directory. An unknown node raises UnknownNodeError; it is never "no hits".
2. Decide what may be searched: the items of THIS node only (not its parent, not its children: a decision to
   confirm with the supervisor), the ACTIVE version of each item, and only items whose active version matches the metadata filter.
3. Search the vector index with that filter. The index drops everything else before it computes a single score.
4. Rank by cosine similarity, best first; ties break on the chunk id, so the same question gives the same list.

A node sees only its own chunks. Knowledge moves up the hierarchy as transfer packages (Phase 11), never by letting a
parent search its children's chunks, and every question of the answer key is answerable only from the node that asks.
"""
from dataclasses import dataclass, field
from typing import Mapping, Optional

from ..knowledge.metadata import BY_NAME
from ..knowledge.model import KnowledgeChunk, normalize_text
from ..shared.kernel import DomainError
from .citation import Citation
from .vector_index import IndexFilter

DEFAULT_K = 3   # the Phase 2 baseline k (baseline_runner/config.py BASELINE_K)


class IndexOutOfDateError(DomainError):
    """The index holds vectors of another embedding model than the one embedding the question. Run indexing again."""


def _as_filter(metadata):
    pairs = tuple(sorted((str(k), str(v).strip()) for k, v in dict(metadata or {}).items()))
    for name, value in pairs:
        if name not in BY_NAME:
            raise DomainError(f"unknown metadata field {name!r} in a retrieval filter")
        if not value:
            raise DomainError(f"the retrieval filter for {name} has no value")
    return pairs


@dataclass(frozen=True)
class RetrievalQuery:
    """A question as retrieval sees it: normalized text, the asking node, k, and a metadata filter.

    The filter is field -> value over the version metadata (knowledge/metadata.py). A value must be equal, except for
    `tags`, where the value must be one of the item's labels."""
    text: str
    node_id: str
    k: int = DEFAULT_K
    metadata_filter: tuple = field(default=())

    def __post_init__(self):
        object.__setattr__(self, "text", normalize_text(self.text or ""))
        object.__setattr__(self, "node_id", str(self.node_id))
        if not self.text:
            raise DomainError("a retrieval query needs some text")
        if not isinstance(self.k, int) or self.k < 1:
            raise DomainError(f"k is a whole number of at least 1, not {self.k!r}")
        object.__setattr__(self, "metadata_filter", _as_filter(dict(self.metadata_filter)))

    def matches(self, metadata):
        for name, wanted in self.metadata_filter:
            value = metadata.get(name)
            if value is None:
                return False
            if BY_NAME[name].rule == "list":
                if wanted not in [part.strip() for part in value.split(";")]:
                    return False
            elif value != wanted:
                return False
        return True


@dataclass(frozen=True)
class RetrievalHit:
    """One retrieved chunk: its rank (1 is best), its cosine score, and the chunk with its SourceLocation."""
    rank: int
    score: float
    chunk: KnowledgeChunk

    @property
    def chunk_id(self):
        return self.chunk.chunk_id

    @property
    def item_id(self):
        return str(self.chunk.location.item_id)

    @property
    def version_tag(self):
        return str(self.chunk.location.version_tag)

    @property
    def node_id(self):
        return self.chunk.node_id

    @property
    def location(self):
        return self.chunk.location

    @property
    def text(self):
        return self.chunk.text

    def citation(self):
        return Citation.of_chunk(self.chunk)


class Retriever:
    """Retriever(index, embedder, directory, repository).retrieve(question, node_id, k, metadata) -> [RetrievalHit].

    `embedder` needs `model_tag` and `embed_query(text)`; `directory` is a NodeDirectory; `repository` a
    KnowledgeRepository (it says which version of each item is active, and gives the chunks and their locations)."""

    def __init__(self, index, embedder, directory, repository):
        self.index = index
        self.embedder = embedder
        self.directory = directory
        self.repository = repository

    def retrieve(self, question, node_id, k=DEFAULT_K, metadata: Optional[Mapping[str, str]] = None):
        query = question if isinstance(question, RetrievalQuery) else RetrievalQuery(question, node_id, k, tuple((metadata or {}).items()))
        return self.search(query)

    def search(self, query: RetrievalQuery):
        self.directory.require(query.node_id)                          # step 1: UnknownNodeError for an unknown node
        model = str(self.embedder.model_tag)
        stale = {s for s in self.index.signatures() if s.embedding_model != model}
        if stale:
            raise IndexOutOfDateError(f"the index holds vectors of {sorted(s.embedding_model for s in stale)}, "
                                      f"but questions are embedded with {model}; index the knowledge again")

        chunks, allowed = {}, set()                                    # step 2: own node, active version, metadata
        for item in self.repository.items_of_node(query.node_id):
            active = item.active_version
            if item.node_id != query.node_id or not query.matches(active.metadata):
                continue
            allowed.add((str(item.item_id), str(active.tag)))
            chunks.update((c.chunk_id, c) for c in active.chunks)
        if not allowed:
            return []

        vector = self.embedder.embed_query(query.text)                 # steps 3 and 4
        found = self.index.search(vector, query.k, IndexFilter(query.node_id, frozenset(allowed)))
        hits = []
        for record, score in found:
            chunk = chunks.get(record.chunk_id)
            if chunk is None or chunk.node_id != query.node_id:        # cannot happen after the filter; never pass it on
                raise DomainError(f"the index returned chunk {record.chunk_id}, which node {query.node_id} may not see")
            hits.append(RetrievalHit(len(hits) + 1, score, chunk))
        return hits
