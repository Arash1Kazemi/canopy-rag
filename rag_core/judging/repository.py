"""The JudgeScoreRepository interface. The adapters are in infrastructure/: InMemoryJudgeRepository (memory_judging.py) and
SqliteJudgeRepository (sqlite_judging.py). Both pass the same contract tests (tests/test_core_judging_storage.py).

Scores are stored a whole run at a time, and a stored score is never changed or removed (the same rule as H04 for versions):
a second judgment of the same text is a new run.
"""
from typing import Protocol


class JudgeScoreRepository(Protocol):
    def add_run(self, scores) -> None:
        """Store all repeats of one run in one transaction: all of them are stored, or none. A run id that is already
        stored is refused, and so is a group that mixes run ids or repeats a repeat number."""

    def run(self, run_id) -> list:
        """The repeats of one run, in repeat order. An unknown run id gives an empty list."""

    def run_ids(self) -> list:
        """Every stored run id, in the order the runs were added."""

    def all_scores(self) -> list:
        """Every stored score: runs in the order they were added, repeats in repeat order."""
