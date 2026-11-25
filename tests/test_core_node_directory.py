"""Test area: Registry and layers (H02, H10), Phase 7 prerequisite: the node directory that issue and retrieval code call."""
import pytest

from core_builders import layered_hierarchy
from rag_core.infrastructure.memory import InMemoryHierarchyRepository
from rag_core.infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from rag_core.organization.directory import HierarchyNodeDirectory, RepositoryNodeDirectory, UnknownNodeError
from rag_core.organization.model import NodeIdentifier
from rag_core.shared.kernel import DomainError


@pytest.fixture(params=["snapshot", "memory", "sqlite"])
def directory(request, tmp_path):
    h = layered_hierarchy()
    if request.param == "snapshot":
        yield HierarchyNodeDirectory(h)
    elif request.param == "memory":
        yield RepositoryNodeDirectory(InMemoryHierarchyRepository(h))
    else:
        repo = SqliteHierarchyRepository(tmp_path / "h.sqlite")
        repo.save(h)
        yield RepositoryNodeDirectory(repo)
        repo.close()


def test_known_nodes_exist_and_unknown_ones_do_not(directory):
    assert all(directory.exists(n) for n in ("N0", "N1", "N6"))
    assert not directory.exists("N99") and not directory.exists("n1")      # ids are exact, never matched loosely


def test_a_node_id_object_works_like_its_text(directory):
    assert directory.exists(NodeIdentifier("N4")) and not directory.exists(NodeIdentifier("N5"))


@pytest.mark.parametrize("bad", ["", " ", "N 1", "N1;", None, 4])
def test_a_malformed_id_does_not_exist_and_is_not_required(directory, bad):
    assert directory.exists(bad) is False
    with pytest.raises(UnknownNodeError):
        directory.require(bad)


def test_only_a_terminal_node_is_terminal(directory):
    assert directory.is_terminal("N3") is True
    assert [directory.is_terminal(n) for n in ("N0", "N1", "N2", "N4", "N6")] == [False] * 5


def test_is_terminal_of_an_unknown_node_is_an_error_not_false(directory):
    with pytest.raises(UnknownNodeError, match="N99"):
        directory.is_terminal("N99")


def test_require_returns_the_node(directory):
    n = directory.require("N6")
    assert str(n.node_id) == "N6" and n.layer.value == 3 and str(n.parent_id) == "N4"


def test_an_unknown_node_error_is_a_domain_error():
    assert issubclass(UnknownNodeError, DomainError)


def test_a_repository_directory_sees_later_changes():
    repo = InMemoryHierarchyRepository(layered_hierarchy())
    directory = RepositoryNodeDirectory(repo)
    h = repo.load()
    h.set_terminal("N2", True)
    repo.save(h)
    assert directory.is_terminal("N2") is True


def test_a_snapshot_directory_sees_the_hierarchy_it_was_given():
    h = layered_hierarchy()
    directory = HierarchyNodeDirectory(h)
    h.set_terminal("N2", True)
    assert directory.is_terminal("N2") is True
