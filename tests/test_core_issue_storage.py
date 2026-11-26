"""Test area: Phase 7 issue storage. The same contract tests run against the in-memory and the SQLite repository
(build plan rule 10). A group is stored whole or not at all, and issues survive a restart."""
import sqlite3

import pytest

from issue_builders import CLOCK, issue, seed_issues
from rag_core.infrastructure.issues_csv import SEED_SOURCE
from rag_core.infrastructure.memory import InMemoryIssueRepository
from rag_core.infrastructure.sqlite_issues import SqliteIssueRepository


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        yield InMemoryIssueRepository()
    else:
        r = SqliteIssueRepository(tmp_path / "issues.sqlite")
        yield r
        r.close()


def test_the_seed_issues_are_stored_unchanged(repo):
    assert repo.is_empty()
    repo.add_all(seed_issues())
    assert not repo.is_empty()
    assert repo.all_issues() == seed_issues()                             # every field, in the same order
    assert repo.get("I03").title == "Pilot extra buses on Route 7" and repo.get("I77") is None


def test_every_field_survives_storage(repo):
    repo.add_all(seed_issues())
    rich = issue("I08", parent_issue_id="I01", position=4, status="analyzing", priority="high", category="data",
                 issue_type="question", metadata={"source": "survey", "wave": "2"}, blocked_by=("I02",),
                 knowledge_ids=("D16",), executor_ids=("P01",), proposed_solution="Re-count at the depot",
                 research_completed=True, review_approved=True)
    repo.add_all([rich])
    assert repo.get("I08") == rich


def test_update_replaces_and_refuses_an_unknown_issue(repo):
    repo.add_all(seed_issues())
    changed = repo.get("I04").with_status("analyzing")
    repo.update(changed)
    assert repo.get("I04").status.value == "analyzing"
    with pytest.raises(ValueError, match="not stored"):
        repo.update(issue("I77"))


def test_a_group_with_a_known_or_repeated_id_stores_nothing(repo):
    repo.add_all(seed_issues())
    with pytest.raises(ValueError, match="already stored: I01"):
        repo.add_all([issue("I08", parent_issue_id="I01", position=4), seed_issues()[0]])
    with pytest.raises(ValueError, match="twice"):
        repo.add_all([issue("I08"), issue("I08")])
    assert repo.get("I08") is None and len(repo.all_issues()) == 7


def test_a_group_with_an_unknown_parent_stores_nothing(repo):
    repo.add_all(seed_issues())
    with pytest.raises(ValueError):
        repo.add_all([issue("I08", parent_issue_id="I01", position=4), issue("I09", parent_issue_id="I77")])
    assert repo.get("I08") is None


def test_a_parent_and_its_sub_issues_can_be_stored_together_in_any_order(repo):
    repo.add_all([issue("I91", parent_issue_id="I90"), issue("I90")])
    assert [str(i.issue_id) for i in repo.all_issues()] in (["I90", "I91"], ["I91", "I90"])


def test_a_new_n6_issue_survives_a_restart(tmp_path):
    path = tmp_path / "project.sqlite"
    first = SqliteIssueRepository(path)
    assert first.import_once(SEED_SOURCE, seed_issues(), CLOCK())
    new = issue("I08", node="N6", title="Bus stop shelters missing on Route 7", position=2)
    first.add_all([new])
    first.close()
    second = SqliteIssueRepository(path)                                 # a new repository on the same file
    assert second.get("I08") == new and len(second.all_issues()) == 8
    assert second.was_imported(SEED_SOURCE)
    assert not second.import_once(SEED_SOURCE, seed_issues(), CLOCK())   # the seed is imported once only
    assert len(second.all_issues()) == 8
    second.close()


def test_sqlite_rolls_back_the_whole_group_when_one_row_fails(tmp_path, monkeypatch):
    repo = SqliteIssueRepository(tmp_path / "issues.sqlite")
    repo.add_all(seed_issues())
    real_insert, calls = repo._insert, []

    def insert_then_fail(row):
        calls.append(row["issue_id"])
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk full (simulated)")
        real_insert(row)
    monkeypatch.setattr(repo, "_insert", insert_then_fail)
    with pytest.raises(ValueError, match="nothing was saved"):
        repo.add_all([issue("I08", parent_issue_id="I01", position=4), issue("I09", parent_issue_id="I01", position=5)])
    monkeypatch.undo()
    assert calls == ["I08", "I09"]                                         # the first row was written, then undone
    assert repo.get("I08") is None and len(repo.all_issues()) == 7
    repo.close()


def test_the_seed_table_of_the_project_database_is_read(tmp_path):
    from rag_core.infrastructure.project_db import migrate
    path = migrate(tmp_path / "project.sqlite")
    repo = SqliteIssueRepository(path)
    rows = repo.seed_rows()
    assert [r["issue_id"] for r in rows] == [f"I0{n}" for n in range(1, 8)]
    repo.close()
    empty = SqliteIssueRepository(tmp_path / "empty.sqlite")
    assert empty.seed_rows() is None
    empty.close()
