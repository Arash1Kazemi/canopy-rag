"""Test area: Phase 10 rubric and strict score parser (proposal 16.1, 16.2). A reply that cannot be read as a valid score is a
failed judgment: the parser never guesses, never repairs, and never raises."""
import json

import pytest

from judge_builders import FULL, reply, scores_with_total
from rag_core.judging.parser import parse_judge_reply
from rag_core.judging.rubric import DEFAULT_RUBRIC, JudgeCriterion, JudgeRubric
from rag_core.shared.kernel import DomainError


# ------------------------------------------------------------------ the rubric
def test_the_default_rubric_is_the_sample_of_proposal_16_1():
    assert [(c.key, c.points) for c in DEFAULT_RUBRIC.criteria] == list(FULL.items())
    assert DEFAULT_RUBRIC.total_points == 20 and DEFAULT_RUBRIC.version == 1 and DEFAULT_RUBRIC.rubric_id == "R1"


def test_a_rubric_must_add_up_to_20():
    with pytest.raises(DomainError, match="add up to 19, not 20"):
        JudgeRubric("R9", 1, (JudgeCriterion("a", "A", 10), JudgeCriterion("b", "B", 9)))


@pytest.mark.parametrize("criteria, message", [
    ((), "at least one criterion"),
    ((JudgeCriterion("a", "A", 10), JudgeCriterion("a", "Again", 10)), "twice"),
])
def test_a_rubric_needs_distinct_criteria(criteria, message):
    with pytest.raises(DomainError, match=message):
        JudgeRubric("R9", 1, criteria)


@pytest.mark.parametrize("key, points", [("Not Snake", 5), ("", 5), ("a", 0), ("a", -1), ("a", 2.5), ("a", True)])
def test_a_criterion_needs_a_snake_case_key_and_whole_positive_points(key, points):
    with pytest.raises(DomainError):
        JudgeCriterion(key, "Name", points)


def test_a_rubric_is_versioned():
    with pytest.raises(DomainError, match="version"):
        JudgeRubric("R9", 0, (JudgeCriterion("a", "A", 20),))


def test_the_rubric_text_for_a_prompt_lists_every_criterion_with_its_points():
    text = DEFAULT_RUBRIC.as_prompt_text()
    assert "faithfulness (0 to 5)" in text and "no_unsupported_claims (0 to 1)" in text
    assert text.count("\n") == len(DEFAULT_RUBRIC.criteria) - 1


# ------------------------------------------------------------------ the parser, happy path
def test_a_valid_reply_is_parsed_in_rubric_order():
    result = parse_judge_reply(reply(18), DEFAULT_RUBRIC)
    assert result.ok and result.error == ""
    assert result.parsed.total == 18
    assert [k for k, _ in result.parsed.scores] == list(FULL)
    assert dict(result.parsed.scores) == scores_with_total(18)
    assert result.parsed.explanation == "The output follows the source."


def test_the_optional_fields_of_proposal_16_2_are_kept():
    raw = reply(19, missing_information=["the budget"], unsupported_claims=["a new road"], suggested_fix="Cite D10.")
    parsed = parse_judge_reply(raw, DEFAULT_RUBRIC).parsed
    assert parsed.missing_information == ("the budget",) and parsed.unsupported_claims == ("a new road",)
    assert parsed.suggested_fix == "Cite D10."


def test_whitespace_around_the_object_is_fine():
    assert parse_judge_reply("\n  " + reply(20) + "  \n", DEFAULT_RUBRIC).ok


def test_zero_is_a_valid_score():
    assert parse_judge_reply(reply(0), DEFAULT_RUBRIC).parsed.total == 0


# ------------------------------------------------------------------ the parser, bad output: each one is a failed judgment
BAD = {
    "empty": "",
    "garbage": "I think this is a good answer, 18 out of 20.",
    "prose before the json": "Here is my score:\n" + reply(20),
    "a code fence": "```json\n" + reply(20) + "\n```",
    "json that is not an object": "[1, 2, 3]",
    "a number only": "18",
    "cut off": reply(20)[:-10],
    "a criterion missing": reply(scores={k: v for k, v in FULL.items() if k != "clarity"}),
    "an unknown criterion": reply(scores={**FULL, "style": 1}),
    "a score above its maximum": reply(scores={**FULL, "faithfulness": 6}),
    "a negative score": reply(scores={**FULL, "clarity": -1}),
    "a total above 20": reply(20, total=21),
    "a total that does not match": reply(20, total=19),
    "a total below zero": reply(scores={k: 0 for k in FULL}, total=-1),
    "a float score": reply(scores={**FULL, "clarity": 1.5}),
    "a float that looks whole": '{"scores": {"faithfulness": 5.0, "completeness": 4, "detail_fit": 3, "uncertainty": 3, '
                                '"clarity": 2, "citability": 2, "no_unsupported_claims": 1}, "total": 20, "explanation": "x"}',
    "a score as text": reply(scores={**FULL, "clarity": "2"}),
    "a boolean score": reply(scores={**FULL, "no_unsupported_claims": True}),
    "a null score": reply(scores={**FULL, "clarity": None}),
    "a total as text": reply(20, total="20"),
    "the scores missing": reply(scores={}),
    "no total": reply(20, total=None),
    "no explanation": reply(20, explanation=None),
    "an empty explanation": reply(20, explanation="  "),
    "the scores not an object": reply(scores=[5, 4, 3, 3, 2, 2, 1]),
    "an unknown field": reply(20, verdict="pass"),
    "a pass flag from the model": reply(20, passed=True),
    "a list that is not text": reply(20, unsupported_claims=[1, 2]),
    "a fix that is not text": reply(20, suggested_fix=5),
    "NaN": '{"scores": {"faithfulness": NaN}, "total": 20, "explanation": "x"}',
    "the same key twice": '{"scores": {"faithfulness": 5}, "scores": {"faithfulness": 5}, "total": 20, "explanation": "x"}',
}


@pytest.mark.parametrize("raw", BAD.values(), ids=BAD.keys())
def test_bad_output_is_a_failed_judgment_with_a_reason(raw):
    result = parse_judge_reply(raw, DEFAULT_RUBRIC)
    assert not result.ok and result.parsed is None and result.error


@pytest.mark.parametrize("raw", [None, 18, b"{}", ["x"]])
def test_a_reply_that_is_not_text_never_raises(raw):
    assert not parse_judge_reply(raw, DEFAULT_RUBRIC).ok


def test_the_error_names_the_problem():
    assert "clarity" in parse_judge_reply(BAD["a criterion missing"], DEFAULT_RUBRIC).error
    assert "total" in parse_judge_reply(BAD["a total that does not match"], DEFAULT_RUBRIC).error
    assert "faithfulness" in parse_judge_reply(BAD["a score above its maximum"], DEFAULT_RUBRIC).error
    assert "JSON" in parse_judge_reply(BAD["garbage"], DEFAULT_RUBRIC).error


def test_the_parser_uses_the_rubric_it_is_given():
    two = JudgeRubric("R2", 1, (JudgeCriterion("facts", "Facts", 12), JudgeCriterion("form", "Form", 8)))
    raw = json.dumps({"scores": {"facts": 12, "form": 8}, "total": 20, "explanation": "ok"})
    assert parse_judge_reply(raw, two).ok
    assert not parse_judge_reply(raw, DEFAULT_RUBRIC).ok
