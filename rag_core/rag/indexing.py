"""The indexing use case (Phase 8A): embed the chunks that may be retrieved and store their vectors.

Which chunks: the chunks of the ACTIVE version of every item. An old version is not embedded (retrieval would filter it
out anyway, A12), and the D12 copy has no chunks at all because ingestion skipped it (A6).

Three rules:
1. Rebuild when the signature changes. If the index holds vectors of another embedding model or another chunking
   policy, every vector is dropped and made again, and the chunks go back to `created` in the life cycle.
2. Idempotent otherwise. A chunk that already has a vector of this signature is not embedded again, so a second run
   embeds nothing.
3. Batches. Chunks are sent to the model `batch_size` at a time; each batch is stored as soon as it is embedded, so a
   run that fails half way keeps what it finished and the next run continues.

The model, the index, the repository and the clock come in as arguments (unit-testing rule 1). With a ChunkLifecycle,
each embedded chunk moves created -> embedded -> checked -> indexed. The `checked` step is the duplicate check: an exact
repeat was already skipped at ingestion, and near duplicates and overlaps are advice only (A13), so nothing here
blocks a chunk. A chunk that already has a vector moves straight to `indexed`, which is how the stages are rebuilt after
a restart: the index is the durable record of the `indexed` stage (A12).
"""
from dataclasses import dataclass

from ..knowledge.lifecycle import ChunkStage, next_stage
from ..shared.kernel import DomainError
from .vector_index import IndexSignature, VectorRecord

DEFAULT_BATCH_SIZE = 16


class IndexingError(DomainError):
    """The embedding model gave a wrong answer (a missing vector, or vectors of different lengths)."""


@dataclass(frozen=True)
class IndexingReport:
    signature: IndexSignature
    eligible: int        # chunks of active versions
    embedded: int        # embedded in this run
    kept: int            # already indexed with this signature
    rebuilt: bool        # the index held another signature and was dropped
    batches: int
    indexed_at: str


def _policy_name(chunking_policy):
    name = getattr(chunking_policy, "name", chunking_policy)
    if not isinstance(name, str) or not name.strip():
        raise DomainError("indexing needs the name of the chunking policy the knowledge was cut with")
    return name


def _to_indexed(lifecycle, chunk_id):
    """Move a chunk forward until it is indexed, one step at a time (the life cycle never skips a step)."""
    while lifecycle.stage(chunk_id) != ChunkStage.INDEXED:
        lifecycle.advance(chunk_id, next_stage(lifecycle.stage(chunk_id)))


def index_chunks(repository, index, embedder, *, chunking_policy, clock, lifecycle=None,
                 batch_size=DEFAULT_BATCH_SIZE):
    """Embed the active chunks that have no vector of this signature yet, and store them. Returns an IndexingReport.

    `chunking_policy` is the policy (or its name) the repository's knowledge was cut with; ingestion knows it, the
    chunks do not, so the caller passes it. `embedder.model_tag` names the model."""
    if batch_size < 1:
        raise DomainError(f"batch_size is at least 1, not {batch_size}")
    signature = IndexSignature(str(embedder.model_tag), _policy_name(chunking_policy))
    indexed_at = clock()

    rebuilt = bool(index.signatures()) and index.signatures() != {signature}
    if rebuilt:
        index.clear()

    items = repository.all_items()
    pending, kept = [], 0
    stored = index.chunk_ids()
    for item in items:
        if lifecycle is not None:
            lifecycle.track_item(item)
        for chunk in item.active_version.chunks:
            if lifecycle is not None and rebuilt:
                lifecycle.reset(chunk.chunk_id)
            if chunk.chunk_id in stored:
                kept += 1
                if lifecycle is not None:
                    _to_indexed(lifecycle, chunk.chunk_id)
            else:
                pending.append((item, chunk))

    batches = 0
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        vectors = list(embedder.embed([chunk.text for _, chunk in batch]))
        if len(vectors) != len(batch):
            raise IndexingError(f"the embedding model returned {len(vectors)} vectors for {len(batch)} chunks")
        if len({len(v) for v in vectors}) > 1:
            raise IndexingError("the embedding model returned vectors of different lengths in one batch")
        records = [VectorRecord(chunk.chunk_id, str(item.item_id), str(chunk.location.version_tag), item.node_id,
                                signature.embedding_model, signature.chunking_policy, tuple(vector), indexed_at)
                   for (item, chunk), vector in zip(batch, vectors)]
        index.add(records)
        batches += 1
        if lifecycle is not None:
            for _, chunk in batch:
                _to_indexed(lifecycle, chunk.chunk_id)

    eligible = kept + len(pending)
    return IndexingReport(signature, eligible, len(pending), kept, rebuilt, batches, indexed_at)
