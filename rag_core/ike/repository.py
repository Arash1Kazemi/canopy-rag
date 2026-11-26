"""The IkeRepository interface. The adapters are in infrastructure/: InMemoryIkeRepository (memory_ike.py) and
SqliteIkeRepository (sqlite_ike.py, table `ike_relations`). Both pass the same contract tests
(tests/test_core_ike_storage.py)."""
from typing import Protocol


class IkeRepository(Protocol):
    def add_all(self, relations) -> None:
        """Add new relations in one transaction: all of them are stored, or none. A known edge is refused (ValueError)."""

    def all_relations(self) -> list:
        """Every stored relation, sorted by node, then the 13.1 order of the type, then source and target."""

    def relations_of_node(self, node_id) -> list:
        """The relations of one node only, in the same order."""

    def contains(self, relation) -> bool:
        """True when an edge with the same type, source and target is stored."""

    def is_empty(self) -> bool:
        """True when no relation is stored."""
