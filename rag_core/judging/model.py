"""The JudgeScore entity and the repeatability check (Phase 10, proposal 16.2 and metric M20).

A JudgeScore is one stored judgment: which run and repeat it belongs to, which prompt, rubric and model made it, the raw reply
of the model, what the parser read from it, and the outcome. The outcome is decided by the system, never by the model:

    pass     the reply was valid and the total reached the threshold of the target layer
    fail     the reply was valid and the total is below the threshold
    invalid  the reply could not be read as a valid score (a failed judgment, never a pass)

The class refuses to be built in a state that would let an invalid judgment look like a pass (hard rule H05 starts here: the
transfer package is judged, and below the threshold it is never sent).
"""
from dataclasses import dataclass
from typing import Optional

from ..shared.kernel import DomainError
from .threshold import JudgeThreshold

PASS, FAIL, INVALID = "pass", "fail", "invalid"
OUTCOMES = (PASS, FAIL, INVALID)


@dataclass(frozen=True)
class JudgeScore:
    run_id: str
    repeat: int
    prompt_id: str
    prompt_version: int
    rubric_id: str
    rubric_version: int
    model_tag: str
    target_layer: int
    threshold: int
    text_sha256: str
    source_ref: str
    raw_output: str
    parse_ok: bool
    parse_error: str
    scores: tuple
    total: Optional[int]
    explanation: str
    missing_information: tuple
    unsupported_claims: tuple
    suggested_fix: str
    outcome: str
    judged_at: str

    def __post_init__(self):
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise DomainError("a judge score needs a run id")
        if not isinstance(self.repeat, int) or isinstance(self.repeat, bool) or self.repeat < 1:
            raise DomainError(f"the repeat number starts at 1, not {self.repeat!r}")
        if self.outcome not in OUTCOMES:
            raise DomainError(f"outcome must be one of {', '.join(OUTCOMES)}, not {self.outcome!r}")
        if self.parse_ok:
            if self.total is None:
                raise DomainError("a valid judgment has a total")
            expected = PASS if JudgeThreshold(self.threshold).passes(self.total) else FAIL
            if self.outcome != expected:
                raise DomainError(f"a total of {self.total} against the threshold {self.threshold} is a {expected}, not {self.outcome!r}")
        else:
            if self.outcome != INVALID:
                raise DomainError("a failed judgment is invalid: it is never a pass and never an ordinary fail")
            if self.total is not None or self.scores:
                raise DomainError("a failed judgment has no total and no scores")
            if not self.parse_error:
                raise DomainError("a failed judgment says why it failed")

    @property
    def passed(self):
        return self.outcome == PASS


@dataclass(frozen=True)
class Repeatability:
    """Several runs of the judge on the same input with the same settings (metric M20).

    same_decision: every repeat was valid and all gave the same pass or not-pass decision. A failed judgment is never counted
    as agreement, so a judge that writes garbage twice does not look repeatable. same_total: every repeat was valid and
    gave the same total."""
    run_id: str
    runs: int
    outcomes: tuple
    totals: tuple
    any_invalid: bool
    same_decision: bool
    same_total: bool


def repeatability_of(scores):
    """The repeatability of the repeats of one judge run (two or more JudgeScore objects of the same run)."""
    scores = list(scores)
    if len(scores) < 2:
        raise DomainError("repeatability needs at least two repeats")
    if len({s.run_id for s in scores}) != 1:
        raise DomainError("repeatability compares the repeats of one run")
    invalid = any(s.outcome == INVALID for s in scores)
    return Repeatability(
        run_id=scores[0].run_id, runs=len(scores), outcomes=tuple(s.outcome for s in scores),
        totals=tuple(s.total for s in scores), any_invalid=invalid,
        same_decision=not invalid and len({s.passed for s in scores}) == 1,
        same_total=not invalid and len({s.total for s in scores}) == 1)


def repeatability_share(items):
    """M20: the share of items (Repeatability objects, one per judged input) with the same decision. None for no items."""
    items = list(items)
    if not items:
        return None
    return sum(1 for r in items if r.same_decision) / len(items)
