"""Test area: Registry and layers, Phase 6: the city hierarchy survives a restart (a new repository on the same file)."""
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from rag_core.organization.directory import RepositoryNodeDirectory
from rag_core.shared.kernel import TransferDetailLevel

NODES, LAYERS = "registry/node_layer_registry.csv", "registry/layer_registry.csv"


def restart(path):
    """Close nothing and keep nothing: a brand-new repository object on the same file, as after a program restart."""
    return SqliteHierarchyRepository(path)


def test_the_full_city_is_the_same_after_a_restart(tmp_path):
    path = tmp_path / "city.sqlite"
    city = CsvHierarchyRepository(NODES, LAYERS).load()
    first = SqliteHierarchyRepository(path)
    first.save(city)
    first.close()

    second = restart(path)
    again = second.load()
    try:
        assert again.nodes() == city.nodes()
        assert again.layers() == city.layers()
        assert [str(n.node_id) for n in again.terminal_nodes()] == [str(n.node_id) for n in city.terminal_nodes()] == ["N3", "N5"]
        assert {str(n.node_id): str(n.parent_id) for n in again.nodes()} == {str(n.node_id): str(n.parent_id) for n in city.nodes()}
        assert [l.rule for l in again.layers()] == [l.rule for l in city.layers()]
        assert any(l.rule is not None for l in again.layers())          # the test would prove nothing without any rules
        assert again.problems() == []
    finally:
        second.close()


def test_changes_made_before_a_restart_are_still_there_after_it(tmp_path):
    path = tmp_path / "city.sqlite"
    first = SqliteHierarchyRepository(path)
    first.save(CsvHierarchyRepository(NODES, LAYERS).load())
    h = first.load()
    h.move_node("N6", "N2")
    h.set_terminal("N6", True)
    first.save(h)
    first.close()

    second = restart(path)
    try:
        again = second.load()
        assert str(again.parent("N6").node_id) == "N2" and again.node("N6").is_terminal
        assert again.node("N6").reporting_format == TransferDetailLevel.MANAGERIAL
        assert again.nodes() == h.nodes() and again.layers() == h.layers()
    finally:
        second.close()


def test_the_node_directory_works_on_the_restarted_file(tmp_path):
    path = tmp_path / "city.sqlite"
    first = SqliteHierarchyRepository(path)
    first.save(CsvHierarchyRepository(NODES, LAYERS).load())
    first.close()

    second = restart(path)
    try:
        directory = RepositoryNodeDirectory(second)
        assert directory.exists("N6") and not directory.exists("N7")
        assert directory.is_terminal("N5") and not directory.is_terminal("N4")
    finally:
        second.close()
