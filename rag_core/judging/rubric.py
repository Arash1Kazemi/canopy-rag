"""The judge rubric (Phase 10, proposal 16.1): the criteria the judge scores, with their points, adding up to 20.

A rubric is versioned (id and version), so a stored score always says which rubric produced it. Change a rubric by making
a new version, never by editing an old one (decision A68). Pure domain code: no file, no model.
"""
import re
from dataclasses import dataclass

from ..shared.kernel import DomainError

RUBRIC_TOTAL = 20                         # proposal 16.1: the default score is 20
KEY = re.compile(r"[a-z][a-z0-9_]*")


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class JudgeCriterion:
    """One line of the rubric: a key the judge answers with, a name for people, and the points it is worth."""
    key: str
    name: str
    points: int

    def __post_init__(self):
        if not isinstance(self.key, str) or KEY.fullmatch(self.key) is None:
            raise DomainError(f"a criterion key is snake_case, not {self.key!r}")
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainError(f"criterion {self.key} needs a name")
        if not _whole(self.points) or self.points < 1:
            raise DomainError(f"criterion {self.key}: points are a whole number from 1, not {self.points!r}")


@dataclass(frozen=True)
class JudgeRubric:
    """The scoring framework: criteria that add up to 20 points."""
    rubric_id: str
    version: int
    criteria: tuple

    def __post_init__(self):
        if not isinstance(self.rubric_id, str) or not self.rubric_id.strip():
            raise DomainError("a rubric needs an id")
        if not _whole(self.version) or self.version < 1:
            raise DomainError(f"rubric {self.rubric_id}: the version is a whole number from 1, not {self.version!r}")
        if not self.criteria:
            raise DomainError(f"rubric {self.rubric_id} needs at least one criterion")
        keys = [c.key for c in self.criteria]
        if len(set(keys)) != len(keys):
            raise DomainError(f"rubric {self.rubric_id} lists a criterion key twice")
        if self.total_points != RUBRIC_TOTAL:
            raise DomainError(f"rubric {self.rubric_id}: the criteria add up to {self.total_points}, not {RUBRIC_TOTAL}")

    @property
    def total_points(self):
        return sum(c.points for c in self.criteria)

    @property
    def keys(self):
        return tuple(c.key for c in self.criteria)

    def criterion(self, key):
        return next(c for c in self.criteria if c.key == key)

    def as_prompt_text(self):
        """One line per criterion, for the {{rubric}} blank of the judge prompt."""
        return "\n".join(f"- {c.key} (0 to {c.points}): {c.name}" for c in self.criteria)


# Decision A68: the criteria and points of the sample rubric in proposal 16.1, as written there.
DEFAULT_RUBRIC = JudgeRubric("R1", 1, (
    JudgeCriterion("faithfulness", "Faithful to the source knowledge", 5),
    JudgeCriterion("completeness", "Complete against the user's request", 4),
    JudgeCriterion("detail_fit", "Level of detail fits the target layer", 3),
    JudgeCriterion("uncertainty", "Uncertainty and gaps are handled correctly", 3),
    JudgeCriterion("clarity", "Clear and professionally structured", 2),
    JudgeCriterion("citability", "Can be traced back to a source", 2),
    JudgeCriterion("no_unsupported_claims", "No claim without support", 1),
))
