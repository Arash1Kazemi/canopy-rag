"""The judge threshold, one per layer (Phase 10, proposal 16.1, decision A69).

A score passes when it is at least the minimum judge score of the layer that RECEIVES the output (the target layer). The
number lives in the layer registry (`min_judge_score` of the layer's TransferRule), so the supervisor changes it in one
place and the judge reads it from there. Nothing here holds a number of its own except the proposal's default, 18 out of 20,
which is used only when a layer that receives packages has a rule with no score. A layer with no rule receives nothing, so
it has no threshold, and asking for it is an error: there is no silent fallback.
"""
from dataclasses import dataclass

from ..shared.kernel import DomainError
from .rubric import RUBRIC_TOTAL

PROPOSAL_DEFAULT_MIN_SCORE = 18          # proposal 16.1: "18 out of 20" for important outputs


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class JudgeThreshold:
    """The minimum accepted score, out of 20."""
    min_score: int

    def __post_init__(self):
        if not _whole(self.min_score) or not 1 <= self.min_score <= RUBRIC_TOTAL:
            raise DomainError(f"a judge threshold is a whole number from 1 to {RUBRIC_TOTAL}, not {self.min_score!r}")

    def passes(self, score):
        """True when the score is a whole number from 0 to 20 that reaches the threshold. Anything else is never a pass."""
        return _whole(score) and 0 <= score <= RUBRIC_TOTAL and score >= self.min_score


class ThresholdPolicy:
    """The threshold and the detail level of every layer that receives packages."""

    def __init__(self, entries, known_layers=()):
        """`entries` maps a layer index to (JudgeThreshold, detail level text). `known_layers` are all layers of the registry,
        so the error can tell "receives nothing" from "not in the registry"."""
        self._entries = dict(entries)
        self._known = set(known_layers) | set(self._entries)

    def layers(self):
        return tuple(sorted(self._entries))

    def _entry(self, layer):
        if layer in self._entries:
            return self._entries[layer]
        if layer in self._known:
            raise DomainError(f"layer {layer} receives nothing, so it has no judge threshold")
        raise DomainError(f"layer {layer} is not in the registry")

    def threshold_for(self, layer):
        return self._entry(layer)[0]

    def detail_level_for(self, layer):
        return self._entry(layer)[1]


def threshold_policy_from_hierarchy(hierarchy):
    """Read the policy from the layer registry held by the Hierarchy."""
    entries = {}
    known = set()
    for layer in hierarchy.layers():
        known.add(layer.index.value)
        rule = layer.rule
        if rule is None:
            continue
        minimum = rule.min_judge_score if rule.min_judge_score is not None else PROPOSAL_DEFAULT_MIN_SCORE
        entries[layer.index.value] = (JudgeThreshold(minimum), rule.detail_level.value)
    return ThresholdPolicy(entries, known)
