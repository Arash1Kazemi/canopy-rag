"""Test area: Phase 10 judge score storage. The same contract tests run against the in-memory and the SQLite repository
(build plan rule 10). A run is stored whole or not at all, a stored run is never replaced, and scores survive a restart."""
from dataclasses import replace

import pytest

from judge_builders import reply
from rag_core.infrastructure.memory_judging import InMemoryJudgeRepository
from rag_core.infrastructure.sqlite_judging import SqliteJudgeRepository
from rag_core.judging.model import FAIL, INVALID, PASS, JudgeScore
from rag_core.judging.parser import parse_judge_reply
from rag_core.judging.rubric import DEFAULT_RUBRIC


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        yield InMemoryJudgeRepository()
    else:
        r = SqliteJudgeRepository(tmp_path / "judge.sqlite")
        yield r
        r.close()


def score(run_id="J1", repeat=1, raw=None, threshold=18, **changes):
    raw = reply(20) if raw is None else raw
    parsed = parse_judge_reply(raw, DEFAULT_RUBRIC)
    values = dict(
        run_id=run_id, repeat=repeat, prompt_id="P14", prompt_version=1, rubric_id="R1", rubric_version=1, model_tag="stub-judge",
        target_layer=1, threshold=threshold, text_sha256="a" * 64, source_ref="D10", raw_output=raw, parse_ok=parsed.ok,
        parse_error=parsed.error, scores=parsed.parsed.scores if parsed.ok else (), total=parsed.parsed.total if parsed.ok else None,
        explanation=parsed.parsed.explanation if parsed.ok else "", missing_information=("the budget",) if parsed.ok else (),
        unsupported_claims=(), suggested_fix="Cite D10." if parsed.ok else "", outcome=INVALID, judged_at="2026-11-26T10:00:00Z")
    if parsed.ok:
        values["outcome"] = PASS if parsed.parsed.total >= threshold else FAIL
    values.update(changes)
    return JudgeScore(**values)


def test_a_run_comes_back_exactly_as_it_went_in(repo):
    run = [score(repeat=1), score(repeat=2, raw=reply(17))]
    repo.add_run(run)
    assert repo.run("J1") == run
    assert [s.outcome for s in repo.run("J1")] == [PASS, FAIL]


def test_a_failed_judgment_is_stored_with_its_raw_reply(repo):
    repo.add_run([score(raw="I would say 19 out of 20.")])
    stored = repo.run("J1")[0]
    assert stored.outcome == INVALID and not stored.passed and stored.total is None
    assert stored.raw_output == "I would say 19 out of 20." and "JSON" in stored.parse_error


def test_an_unknown_run_is_an_empty_list(repo):
    assert repo.run("nope") == [] and repo.run_ids() == [] and repo.all_scores() == []


def test_run_ids_and_scores_keep_the_order_they_were_added(repo):
    repo.add_run([score("B", 1), score("B", 2)])
    repo.add_run([score("A", 1)])
    assert repo.run_ids() == ["B", "A"]
    assert [(s.run_id, s.repeat) for s in repo.all_scores()] == [("B", 1), ("B", 2), ("A", 1)]


def test_a_run_id_that_is_stored_is_never_replaced(repo):
    repo.add_run([score("J1", 1)])
    with pytest.raises(ValueError, match="already stored"):
        repo.add_run([score("J1", 1, raw=reply(10))])
    assert repo.run("J1")[0].total == 20


def test_a_group_with_a_repeated_repeat_number_stores_nothing(repo):
    with pytest.raises(ValueError, match="twice"):
        repo.add_run([score("J1", 1), score("J1", 1)])
    assert repo.run_ids() == []


def test_a_group_that_mixes_run_ids_is_refused(repo):
    with pytest.raises(ValueError, match="one run"):
        repo.add_run([score("J1", 1), score("J2", 2)])
    assert repo.run_ids() == []


def test_an_empty_group_is_refused(repo):
    with pytest.raises(ValueError, match="no scores"):
        repo.add_run([])


def test_the_threshold_that_was_used_is_stored_with_the_score(repo):
    repo.add_run([score("J1", 1, raw=reply(17), threshold=16)])
    stored = repo.run("J1")[0]
    assert stored.threshold == 16 and stored.outcome == PASS


def test_the_domain_refuses_a_pass_for_a_failed_judgment():
    with pytest.raises(Exception, match="never a pass"):
        replace(score(raw="garbage"), outcome=PASS)


def test_the_domain_refuses_an_outcome_that_disagrees_with_the_threshold():
    with pytest.raises(Exception, match="is a fail"):
        replace(score(raw=reply(17)), outcome=PASS)


def test_scores_survive_a_restart(tmp_path):
    path = tmp_path / "judge.sqlite"
    first = SqliteJudgeRepository(path)
    run = [score(repeat=1), score(repeat=2, raw="garbage")]
    first.add_run(run)
    first.close()
    second = SqliteJudgeRepository(path)
    assert second.run("J1") == run
    second.close()
