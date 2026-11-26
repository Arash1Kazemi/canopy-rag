"""Test area: Phase 10 threshold per layer (decision A69). A score passes when it is at least the minimum judge score of the
layer that receives the output. The number is read from the layer registry, so the supervisor changes it in one place."""
import pytest

from core_builders import layered_hierarchy, rule
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.judging.threshold import PROPOSAL_DEFAULT_MIN_SCORE, JudgeThreshold, threshold_policy_from_hierarchy
from rag_core.shared.kernel import DomainError

from pathlib import Path

REGISTRY = Path("registry")


# ------------------------------------------------------------------ the value object
@pytest.mark.parametrize("score, expected", [(17, False), (18, True), (19, True), (20, True), (0, False)])
def test_edges_around_18_out_of_20(score, expected):
    assert JudgeThreshold(18).passes(score) is expected


def test_the_proposal_default_is_18():
    assert PROPOSAL_DEFAULT_MIN_SCORE == 18


@pytest.mark.parametrize("bad", [0, 21, -3, 17.5, "18", True, None])
def test_a_threshold_is_a_whole_number_from_1_to_20(bad):
    with pytest.raises(DomainError):
        JudgeThreshold(bad)


@pytest.mark.parametrize("bad", [21, -1, 18.0, "18", None, True])
def test_a_score_outside_0_to_20_is_never_a_pass(bad):
    assert JudgeThreshold(1).passes(bad) is False


# ------------------------------------------------------------------ the policy, read from the hierarchy
def test_every_layer_that_receives_something_has_the_default_18():
    policy = threshold_policy_from_hierarchy(layered_hierarchy())
    assert [policy.threshold_for(i).min_score for i in (0, 1, 2)] == [18, 18, 18]
    assert policy.layers() == (0, 1, 2)


def test_the_policy_of_the_real_layer_registry_is_18_for_layers_0_to_2():
    h = CsvHierarchyRepository(REGISTRY / "node_layer_registry.csv", REGISTRY / "layer_registry.csv").load()
    policy = threshold_policy_from_hierarchy(h)
    assert [policy.threshold_for(i).min_score for i in (0, 1, 2)] == [18, 18, 18]


def test_a_layer_that_receives_nothing_has_no_threshold_and_no_fallback():
    policy = threshold_policy_from_hierarchy(layered_hierarchy())     # layer 3 has no transfer rule
    with pytest.raises(DomainError, match="layer 3 receives nothing"):
        policy.threshold_for(3)
    with pytest.raises(DomainError, match="not in the registry"):
        policy.threshold_for(7)


def test_changing_the_score_of_one_layer_changes_only_that_layer():
    h = layered_hierarchy()
    h.set_layer_rule(1, rule("managerial", score=16))
    policy = threshold_policy_from_hierarchy(h)
    assert policy.threshold_for(1).min_score == 16
    assert policy.threshold_for(0).min_score == 18 and policy.threshold_for(2).min_score == 18
    assert policy.threshold_for(1).passes(16) and not policy.threshold_for(0).passes(16)


def test_a_rule_with_no_score_takes_the_proposal_default_18():
    h = layered_hierarchy()
    h.set_layer_rule(2, rule("technical_summary", score=None))
    assert threshold_policy_from_hierarchy(h).threshold_for(2).min_score == 18


def test_the_policy_also_gives_the_detail_level_the_layer_wants():
    policy = threshold_policy_from_hierarchy(layered_hierarchy())
    assert [policy.detail_level_for(i) for i in (0, 1, 2)] == ["executive", "managerial", "technical_summary"]
