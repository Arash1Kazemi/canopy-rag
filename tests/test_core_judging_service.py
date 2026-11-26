"""Test area: Phase 10 judge use case, with a stub judge. A run asks the model one or more times, reads each reply with the strict
parser, decides pass or fail against the threshold of the target layer, stores every repeat, and computes repeatability (M20).
No model is called."""
from pathlib import Path

import pytest

from core_builders import layered_hierarchy, rule
from judge_builders import reply
from rag_core.fakes import FixedClock, SequenceLanguageModel
from rag_core.infrastructure.memory_judging import InMemoryJudgeRepository
from rag_core.infrastructure.sqlite_judging import SqliteJudgeRepository
from rag_core.judging.judge import JudgeService
from rag_core.judging.model import FAIL, INVALID, PASS, repeatability_of, repeatability_share
from rag_core.judging.prompt import JudgePrompt
from rag_core.judging.rubric import DEFAULT_RUBRIC
from rag_core.judging.threshold import threshold_policy_from_hierarchy
from rag_core.shared.kernel import DomainError

TEMPLATE = Path("prompts/judge_rubric_v1.txt").read_text(encoding="utf-8")
PROMPT = JudgePrompt("P14", 1, TEMPLATE[:-1])
TEXT = "The Transit Agency has 135 buses [D10_bus_fleet_inventory_v2]."


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        yield InMemoryJudgeRepository()
    else:
        r = SqliteJudgeRepository(tmp_path / "judge.sqlite")
        yield r
        r.close()


def service(model, repo, hierarchy=None):
    policy = threshold_policy_from_hierarchy(hierarchy or layered_hierarchy())
    return JudgeService(model, repo, DEFAULT_RUBRIC, PROMPT, policy, FixedClock("2026-11-26T10:00:00Z"))


# ------------------------------------------------------------------ one judgment
def test_a_perfect_reply_passes_and_everything_is_recorded(repo):
    model = SequenceLanguageModel(reply(20), model_tag="phi4-mini:3.8b")
    result = service(model, repo).judge(TEXT, 1, run_id="J1", runs=1, source_ref="D10")
    (s,) = result.scores
    assert s.outcome == PASS and s.passed and s.total == 20 and s.threshold == 18 and s.target_layer == 1
    assert (s.run_id, s.repeat, s.prompt_id, s.prompt_version, s.rubric_id, s.rubric_version) == ("J1", 1, "P14", 1, "R1", 1)
    assert s.model_tag == "phi4-mini:3.8b" and s.raw_output == reply(20) and s.source_ref == "D10"
    assert s.judged_at == "2026-11-26T10:00:00Z" and len(s.text_sha256) == 64
    assert dict(s.scores)["faithfulness"] == 5
    assert repo.run("J1") == [s]
    assert result.repeatability is None


@pytest.mark.parametrize("total, outcome", [(17, FAIL), (18, PASS), (19, PASS), (20, PASS), (0, FAIL)])
def test_threshold_edges_17_18_19(repo, total, outcome):
    result = service(SequenceLanguageModel(reply(total)), repo).judge(TEXT, 0, run_id="J1", runs=1)
    assert result.scores[0].outcome == outcome and result.scores[0].total == total


def test_the_threshold_is_the_one_of_the_target_layer(repo):
    h = layered_hierarchy()
    h.set_layer_rule(1, rule("managerial", score=16))
    j = service(SequenceLanguageModel(reply(17)), repo, h)
    assert j.judge(TEXT, 1, run_id="at-layer-1", runs=1).scores[0].outcome == PASS      # 17 >= 16
    assert j.judge(TEXT, 0, run_id="at-layer-0", runs=1).scores[0].outcome == FAIL      # 17 < 18
    assert [s.threshold for s in repo.all_scores()] == [16, 18]


def test_a_layer_that_receives_nothing_is_refused_before_the_model_is_called(repo):
    model = SequenceLanguageModel(reply(20))
    with pytest.raises(DomainError, match="layer 3 receives nothing"):
        service(model, repo).judge(TEXT, 3, run_id="J1")
    assert model.prompts == [] and repo.run_ids() == []


# ------------------------------------------------------------------ bad output is a failed judgment, never a pass
@pytest.mark.parametrize("raw", [
    "Score: 20/20, excellent.",                           # garbage
    "",                                                   # empty
    reply(20, total=25),                                  # total above 20 would reach any threshold
    reply(20, total=19),                                  # total does not match the criteria
    reply(scores={"faithfulness": 5}),                    # criteria missing
    reply(20, passed=True),                               # the model tries to decide the outcome itself
    "```json\n" + reply(20) + "\n```",                    # a code fence is not repaired
])
def test_a_reply_that_cannot_be_read_is_a_failed_judgment(repo, raw):
    result = service(SequenceLanguageModel(raw), repo).judge(TEXT, 2, run_id="J1", runs=1)
    (s,) = result.scores
    assert s.outcome == INVALID and not s.passed and s.total is None and not s.parse_ok
    assert s.raw_output == raw and s.parse_error
    assert repo.run("J1") == [s]


# ------------------------------------------------------------------ repeatability (M20)
def test_two_identical_runs_agree(repo):
    result = service(SequenceLanguageModel(reply(19)), repo).judge(TEXT, 1, run_id="J1", runs=2)
    r = result.repeatability
    assert [s.repeat for s in result.scores] == [1, 2] and r.runs == 2
    assert r.same_decision and r.same_total and not r.any_invalid
    assert [s.repeat for s in repo.run("J1")] == [1, 2]            # both runs are recorded


def test_two_runs_on_either_side_of_the_threshold_disagree(repo):
    r = service(SequenceLanguageModel(reply(17), reply(18)), repo).judge(TEXT, 1, run_id="J1").repeatability
    assert not r.same_decision and not r.same_total
    assert r.outcomes == (FAIL, PASS) and r.totals == (17, 18)


def test_different_totals_with_the_same_decision_are_recorded_as_such(repo):
    r = service(SequenceLanguageModel(reply(19), reply(20)), repo).judge(TEXT, 1, run_id="J1").repeatability
    assert r.same_decision and not r.same_total


def test_a_failed_judgment_is_never_agreement(repo):
    r = service(SequenceLanguageModel("garbage", reply(20)), repo).judge(TEXT, 1, run_id="J1").repeatability
    assert r.any_invalid and not r.same_decision
    again = service(SequenceLanguageModel("garbage", "other garbage"), repo).judge(TEXT, 1, run_id="J2").repeatability
    assert again.any_invalid and not again.same_decision           # two bad replies do not make a repeatable judge


def test_the_repeats_are_asked_with_the_same_prompt(repo):
    model = SequenceLanguageModel(reply(20))
    service(model, repo).judge(TEXT, 1, run_id="J1", runs=3)
    assert len(model.prompts) == 3 and len(set(model.prompts)) == 1


def test_m20_is_the_share_of_items_with_the_same_decision(repo):
    agree = service(SequenceLanguageModel(reply(20)), repo).judge(TEXT, 1, run_id="A").repeatability
    split = service(SequenceLanguageModel(reply(10), reply(20)), repo).judge(TEXT, 1, run_id="B").repeatability
    assert repeatability_share([agree, split]) == 0.5
    assert repeatability_share([]) is None


def test_repeatability_needs_two_repeats_of_one_run(repo):
    one = service(SequenceLanguageModel(reply(20)), repo).judge(TEXT, 1, run_id="J1", runs=1).scores
    with pytest.raises(DomainError, match="at least two"):
        repeatability_of(one)
    a = service(SequenceLanguageModel(reply(20)), repo).judge(TEXT, 1, run_id="A", runs=1).scores
    b = service(SequenceLanguageModel(reply(20)), repo).judge(TEXT, 1, run_id="B", runs=1).scores
    with pytest.raises(DomainError, match="one run"):
        repeatability_of(a + b)


# ------------------------------------------------------------------ the prompt
def test_the_prompt_carries_the_rubric_the_detail_level_the_text_the_source_and_the_request(repo):
    model = SequenceLanguageModel(reply(20))
    service(model, repo).judge(TEXT, 1, run_id="J1", runs=1, source="D10 says 135 buses.", request="Report the fleet size.")
    prompt = model.prompts[0]
    assert DEFAULT_RUBRIC.as_prompt_text() in prompt
    assert "needs: managerial" in prompt and TEXT in prompt
    assert "D10 says 135 buses." in prompt and "Report the fleet size." in prompt


def test_a_missing_source_or_request_says_so(repo):
    model = SequenceLanguageModel(reply(20))
    service(model, repo).judge(TEXT, 1, run_id="J1", runs=1)
    assert model.prompts[0].count("(not given)") == 2


def test_a_blank_like_text_in_the_output_is_not_filled_again(repo):
    model = SequenceLanguageModel(reply(20))
    service(model, repo).judge("see {{source}} and {{rubric}}", 1, run_id="J1", runs=1, source="THE-SOURCE")
    assert "see {{source}} and {{rubric}}" in model.prompts[0]


def test_a_judge_prompt_needs_exactly_its_five_blanks():
    with pytest.raises(DomainError, match="blanks"):
        JudgePrompt("P04", 1, "Question: {{question}} Answer: {{candidate}}")


# ------------------------------------------------------------------ setup problems are not judgments
def test_a_model_that_cannot_be_reached_stores_nothing(repo):
    model = SequenceLanguageModel(reply(20), RuntimeError("cannot reach Ollama"))
    with pytest.raises(RuntimeError, match="cannot reach"):
        service(model, repo).judge(TEXT, 1, run_id="J1", runs=2)
    assert repo.run_ids() == []                                    # the run is stored whole or not at all


def test_a_run_id_that_is_stored_is_refused_before_the_model_is_called(repo):
    j = service(SequenceLanguageModel(reply(20)), repo)
    j.judge(TEXT, 1, run_id="J1", runs=1)
    model = SequenceLanguageModel(reply(10))
    with pytest.raises(DomainError, match="already stored"):
        service(model, repo).judge(TEXT, 1, run_id="J1", runs=1)
    assert model.prompts == [] and repo.run("J1")[0].total == 20


@pytest.mark.parametrize("kwargs, message", [
    ({"text": "  "}, "nothing to judge"),
    ({"runs": 0}, "runs"),
    ({"run_id": " "}, "run id"),
])
def test_bad_arguments_are_refused_before_the_model_is_called(repo, kwargs, message):
    model = SequenceLanguageModel(reply(20))
    args = {"text": TEXT, "run_id": "J1", "runs": 1, **kwargs}
    with pytest.raises(DomainError, match=message):
        service(model, repo).judge(args.pop("text"), 1, **args)
    assert model.prompts == []
