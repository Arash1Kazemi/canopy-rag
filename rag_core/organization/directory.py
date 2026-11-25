"""The node directory: the one place that answers "does this node exist?" and "is it terminal?".

Issue, retrieval and transfer code validate a node id through it, never by comparing strings. It is a read-only view of
the Hierarchy aggregate, so the tree rules (H02, H10) stay in one place.

Two ways to build it:
- HierarchyNodeDirectory(hierarchy): a hierarchy that is already loaded (a snapshot).
- RepositoryNodeDirectory(repository): loads from a HierarchyRepository on every question, so it always sees the
  stored tree (the SQLite one, or the in-memory one). A hierarchy has a handful of nodes, so the cost is small.
"""
from typing import Protocol

from ..shared.kernel import DomainError
from .model import Hierarchy, Node, NodeIdentifier
from .repository import HierarchyRepository


class UnknownNodeError(DomainError):
    """A node id that is not in the hierarchy (or is not a valid node id at all)."""


class NodeDirectory(Protocol):
    def exists(self, node_id) -> bool:
        """True when the node is in the hierarchy. A malformed id (empty, spaces, None) is simply False."""

    def is_terminal(self, node_id) -> bool:
        """True when the node is a terminal node (a black box). Raises UnknownNodeError for an unknown node."""

    def require(self, node_id) -> Node:
        """The node, or UnknownNodeError. Use it to validate an id and get the node in one step."""


def _as_identifier(node_id):
    """A NodeIdentifier from a NodeIdentifier or a text; None when it cannot be one."""
    if isinstance(node_id, NodeIdentifier):
        return node_id
    if isinstance(node_id, str):
        try:
            return NodeIdentifier(node_id)
        except DomainError:
            return None
    return None


class HierarchyNodeDirectory:
    def __init__(self, hierarchy: Hierarchy):
        self._hierarchy = hierarchy

    def exists(self, node_id) -> bool:
        key = _as_identifier(node_id)
        return key is not None and self._current().has(key)

    def is_terminal(self, node_id) -> bool:
        return self.require(node_id).is_terminal

    def require(self, node_id) -> Node:
        key = _as_identifier(node_id)
        hierarchy = self._current()
        if key is None or not hierarchy.has(key):
            raise UnknownNodeError(f"unknown node {node_id!r}: it is not in the hierarchy")
        return hierarchy.node(key)

    def _current(self):
        return self._hierarchy


class RepositoryNodeDirectory(HierarchyNodeDirectory):
    def __init__(self, repository: HierarchyRepository):
        self._repository = repository

    def _current(self):
        return self._repository.load()
