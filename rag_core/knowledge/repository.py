"""Storage abstraction for knowledge. The domain and the use cases need only this shape.

infrastructure/memory.py and infrastructure/sqlite.py both provide it, and tests/test_core_storage.py runs the same
tests against both, so either one can be used without changing a use case.
"""
from typing import Iterable, Optional, Protocol

from .model import ContentHash, KnowledgeChunk, KnowledgeItem


class KnowledgeRepository(Protocol):
    def get(self, item_id: str) -> Optional[KnowledgeItem]: ...

    def save(self, item: KnowledgeItem) -> None:
        """Store new versions and the active tag. A stored version is never changed or removed (H04)."""

    def all_items(self) -> list: ...

    def items_of_node(self, node_id: str) -> list: ...

    def find_by_text(self, text_hash: ContentHash) -> list:
        """(item, version) pairs whose normalized text has this fingerprint, in any item."""

    def active_chunks(self, node_id: Optional[str] = None) -> Iterable[KnowledgeChunk]:
        """The chunks of the active version of each item, of one node or of all nodes. RAG (Phase 8) reads these."""
