"""The chunk life cycle (proposal section 7.2): created -> embedded -> checked for duplicates -> indexed.

A chunk moves one step at a time and never skips a step. The one way back is a reset to `created`, used when a chunk
must be embedded again (for example after the embedding model changes).

Retirement is not a stage. A chunk can be retrieved only if it is indexed AND its version is the item's active version.
So switching the active version changes what is retrievable at once, and switching back needs no repair, because the
old chunks were never altered (H04).

The stages are kept in memory here. Where they are stored for good is decided in Phase 8, together with the index
(decision A12 in architecture/architecture.md).
"""
from enum import Enum

from ..shared.kernel import DomainError


class ChunkStage(str, Enum):
    CREATED = "created"
    EMBEDDED = "embedded"
    CHECKED = "checked"        # compared with other knowledge for duplicates and overlaps
    INDEXED = "indexed"


ORDER = (ChunkStage.CREATED, ChunkStage.EMBEDDED, ChunkStage.CHECKED, ChunkStage.INDEXED)


def next_stage(stage):
    """The stage after this one, or None for the last stage."""
    i = ORDER.index(ChunkStage(stage))
    return ORDER[i + 1] if i + 1 < len(ORDER) else None


class ChunkLifecycle:
    def __init__(self):
        self._stages = {}

    def track_item(self, item):
        """Start tracking every chunk of every version of the item, as `created`. A chunk already tracked keeps its stage."""
        for version in item.versions:
            for chunk in version.chunks:
                self._stages.setdefault(chunk.chunk_id, ChunkStage.CREATED)

    def stage(self, chunk_id):
        if chunk_id not in self._stages:
            raise DomainError(f"chunk {chunk_id} is not tracked")
        return self._stages[chunk_id]

    def advance(self, chunk_id, to):
        to = ChunkStage(to)
        current = self.stage(chunk_id)
        if next_stage(current) != to:
            allowed = next_stage(current)
            raise DomainError(f"chunk {chunk_id} is {current.value}: the next stage is "
                              f"{allowed.value if allowed else 'none (it is the last)'}, not {to.value}")
        self._stages[chunk_id] = to
        return to

    def reset(self, chunk_id):
        """Back to `created`, to embed the chunk again."""
        self.stage(chunk_id)
        self._stages[chunk_id] = ChunkStage.CREATED

    def retrievable_chunks(self, item):
        """The chunks retrieval may use for this item: indexed chunks of the active version, in order."""
        return tuple(c for c in item.active_version.chunks if self._stages.get(c.chunk_id) == ChunkStage.INDEXED)
