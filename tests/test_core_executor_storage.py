"""Test area: Phase 9 executor storage. The same contract tests run against the in-memory and the SQLite repository
(build plan rule 10). A group is stored whole or not at all, and executors survive a restart."""
import pytest

from executor_builders import executor, people
from rag_core.infrastructure.memory import InMemoryExecutorRepository
from rag_core.infrastructure.sqlite_executors import SqliteExecutorRepository


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        yield InMemoryExecutorRepository()
    else:
        r = SqliteExecutorRepository(tmp_path / "executors.sqlite")
        yield r
        r.close()


def test_the_seed_people_are_stored_unchanged(repo):
    assert repo.is_empty()
    repo.add_all(people())
    assert repo.all_executors() == people()
    assert repo.get("P01").documents_written == people()[0].documents_written
    assert not repo.is_empty()


def test_an_unknown_executor_is_none(repo):
    assert repo.get("P77") is None


def test_a_group_is_stored_whole_or_not_at_all(repo):
    repo.add_all([executor("P90")])
    with pytest.raises(ValueError, match="already stored"):
        repo.add_all([executor("P91"), executor("P90")])
    assert [str(e.executor_id) for e in repo.all_executors()] == ["P90"]


def test_the_same_id_twice_in_a_group_is_refused(repo):
    with pytest.raises(ValueError, match="twice"):
        repo.add_all([executor("P90"), executor("P90")])
    assert repo.is_empty()


def test_update_replaces_a_stored_executor_and_refuses_an_unknown_one(repo):
    repo.add_all([executor("P90")])
    repo.update(executor("P90", role="Lead", availability="limited", documents_written=(("D15", "Route Redesign"),)))
    again = repo.get("P90")
    assert again.role == "Lead" and again.availability == "limited" and again.documents_written[0].doc_id == "D15"
    with pytest.raises(ValueError, match="not stored"):
        repo.update(executor("P91"))


def test_executors_survive_a_restart(tmp_path):
    path = tmp_path / "executors.sqlite"
    first = SqliteExecutorRepository(path)
    first.add_all(people())
    first.close()
    second = SqliteExecutorRepository(path)
    assert second.all_executors() == people()
    second.close()
