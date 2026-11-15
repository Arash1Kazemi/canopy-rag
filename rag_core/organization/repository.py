"""Storage abstraction for the organization. The domain needs only this shape; infrastructure/ provides it."""
from typing import Protocol

from .model import Hierarchy


class HierarchyRepository(Protocol):
    def load(self) -> Hierarchy: ...


class WritableHierarchyRepository(HierarchyRepository, Protocol):
    """What the workflows need: a hierarchy that can also be saved (the SQLite one; the CSV files are read only)."""
    def save(self, hierarchy: Hierarchy) -> None: ...
