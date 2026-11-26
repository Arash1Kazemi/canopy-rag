"""The ExecutorRepository interface. The adapters are in infrastructure/: InMemoryExecutorRepository (memory.py) and
SqliteExecutorRepository (sqlite_executors.py). The seed CSV is read by infrastructure/executors_csv.py.

Both adapters pass the same contract tests (tests/test_core_executor_storage.py).
"""
from typing import Optional, Protocol


class ExecutorRepository(Protocol):
    def get(self, executor_id) -> Optional[object]:
        """The executor, or None."""

    def all_executors(self) -> list:
        """Every stored executor, in the order they were first added."""

    def add_all(self, executors) -> None:
        """Add new executors in one transaction: all of them are stored, or none. A known id is refused."""

    def update(self, executor) -> None:
        """Replace a stored executor with a changed copy. An unknown id is refused."""

    def is_empty(self) -> bool:
        """True when no executor is stored."""
