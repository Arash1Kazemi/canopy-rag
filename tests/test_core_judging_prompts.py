"""Test area: Phase 10 judge prompts. P14 is registered with task "judge", its file has exactly the five blanks, and the loader
refuses a prompt that is not a rubric judge."""
import pytest

from rag_core.judging.rubric import DEFAULT_RUBRIC
from rag_core.shared.kernel import DomainError
from rag_core.workflows.judge_prompts import DEFAULT_JUDGE_PROMPT, load_judge_prompt


def test_p14_loads_as_version_1_of_the_judge_task():
    prompt = load_judge_prompt()
    assert DEFAULT_JUDGE_PROMPT == "P14" and (prompt.prompt_id, prompt.version) == ("P14", 1)
    assert not prompt.template.endswith("\n")


def test_the_prompt_names_every_criterion_key_only_through_the_rubric_blank():
    template = load_judge_prompt().template
    assert "{{rubric}}" in template
    assert not any(key in template for key in DEFAULT_RUBRIC.keys)       # one source for the criteria: the rubric object


def test_the_prompt_tells_the_model_not_to_decide_pass_or_fail_and_to_reply_with_one_json_object():
    template = load_judge_prompt().template
    assert "Do not write pass or fail" in template and "exactly one JSON object and nothing else" in template


def test_the_phase_2_reference_judge_is_not_a_rubric_judge():
    with pytest.raises(DomainError, match="blanks"):
        load_judge_prompt("P04")


def test_a_prompt_for_another_task_or_an_unknown_id_is_refused():
    with pytest.raises(DomainError, match="not for judging"):
        load_judge_prompt("P01")
    with pytest.raises(DomainError, match="no prompt P99"):
        load_judge_prompt("P99")
