"""Test area: Registry and layers (H02, H10)."""
import pytest

from core_builders import node, small_hierarchy
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.organization.model import Hierarchy, NodeIdentifier
from rag_core.shared.kernel import DomainError, TransferDetailLevel

REGISTRY = "registry/node_layer_registry.csv"


def test_the_city_registry_loads_as_7_nodes_in_4_layers():
    h = CsvHierarchyRepository(REGISTRY).load()
    assert len(h.nodes()) == 7
    assert [len(layer.node_ids) for layer in h.layers()] == [1, 3, 2, 1]


def test_the_path_of_the_bus_project_runs_from_the_council_down():
    h = CsvHierarchyRepository(REGISTRY).load()
    assert [str(n.node_id) for n in h.path("N6")] == ["N0", "N1", "N4", "N6"]


def test_registry_values_become_domain_values():
    n4 = CsvHierarchyRepository(REGISTRY).load().node("N4")
    assert n4.reporting_format == TransferDetailLevel.MANAGERIAL and n4.min_judge_score == 18 and not n4.is_terminal


def test_a_second_root_is_rejected_H02():
    h = small_hierarchy()
    with pytest.raises(DomainError, match="H02"):
        h.add_node(node("N9", 0))


def test_a_child_must_be_one_layer_below_its_parent_H02():
    h = small_hierarchy()
    with pytest.raises(DomainError, match="H02"):
        h.add_node(node("N9", 3, "N1"))


def test_the_root_must_be_in_layer_0_H02():
    with pytest.raises(DomainError, match="H02"):
        Hierarchy().add_node(node("N0", 1))


def test_a_terminal_node_cannot_get_a_child_H10():
    h = small_hierarchy()
    with pytest.raises(DomainError, match="H10"):
        h.add_node(node("N9", 2, "N3"))


def test_a_parent_must_exist_before_its_child():
    with pytest.raises(DomainError, match="does not exist"):
        small_hierarchy().add_node(node("N9", 2, "N7"))


def test_a_node_id_is_never_reused():
    with pytest.raises(DomainError, match="never reused"):
        small_hierarchy().add_node(node("N1", 1, "N0"))


def test_a_node_id_with_a_space_is_rejected():
    with pytest.raises(DomainError):
        NodeIdentifier("N 1")


def test_an_empty_hierarchy_is_not_complete():
    with pytest.raises(DomainError, match="no root"):
        Hierarchy().check_complete()


def test_adding_a_node_records_an_event():
    h = small_hierarchy()
    assert [e.name for e in h.events] == ["NodeAdded"] * 3
