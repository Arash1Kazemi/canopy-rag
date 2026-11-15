"""Test area: Registry and layers (H02, H10), Phase 6: tree queries, move, terminal nodes, node details, layer rules."""
import pytest

from core_builders import layered_hierarchy, node, rule
from rag_core.organization.model import Hierarchy
from rag_core.shared.kernel import Confidentiality, DomainError, TransferDetailLevel


def ids(nodes):
    return [str(n.node_id) for n in nodes]


def bare_hierarchy():
    """No layer registry: N0 > N1, N2 > N4 (under N1)."""
    h = Hierarchy()
    h.add_node(node("N0", 0))
    h.add_node(node("N1", 1, "N0"))
    h.add_node(node("N2", 1, "N0"))
    h.add_node(node("N4", 2, "N1"))
    return h


# --- queries

def test_ancestors_run_from_the_parent_up_to_the_root():
    h = layered_hierarchy()
    assert ids(h.ancestors("N6")) == ["N4", "N1", "N0"] and h.ancestors("N0") == []


def test_descendants_come_level_by_level():
    assert ids(layered_hierarchy().descendants("N0")) == ["N1", "N2", "N3", "N4", "N6"]
    assert layered_hierarchy().descendants("N6") == []


def test_siblings_share_the_parent_and_the_root_has_none():
    h = layered_hierarchy()
    assert ids(h.siblings("N1")) == ["N2", "N3"] and h.siblings("N0") == []


def test_nodes_in_a_layer_and_terminal_nodes():
    h = layered_hierarchy()
    assert ids(h.nodes_in_layer(1)) == ["N1", "N2", "N3"] and ids(h.terminal_nodes()) == ["N3"]


def test_a_layer_carries_its_name_its_rule_and_its_nodes():
    layers = layered_hierarchy().layers()
    assert [l.name for l in layers] == ["Strategic layer", "Parent organizations", "Units", "Projects"]
    assert layers[1].rule.detail_level == TransferDetailLevel.MANAGERIAL and [str(i) for i in layers[1].node_ids] == ["N1", "N2", "N3"]
    assert layers[3].rule is None


def test_a_layer_with_a_registry_entry_but_no_nodes_is_listed():
    h = layered_hierarchy()
    h.define_layer(4, "Sources")
    assert [l.index.value for l in h.layers()] == [0, 1, 2, 3, 4] and h.layers()[4].node_ids == ()


# --- moving a node

def test_a_moved_node_takes_its_subtree_and_shifts_layers():
    h = layered_hierarchy()
    assert [str(i) for i in h.move_node("N4", "N0")] == ["N4", "N6"]
    assert str(h.parent("N4").node_id) == "N0"
    assert (h.node("N4").layer.value, h.node("N6").layer.value) == (1, 2)


def test_a_moved_node_sends_what_the_rule_of_its_new_parent_layer_asks_for():
    h = layered_hierarchy()
    h.move_node("N4", "N0")
    assert h.node("N4").reporting_format == TransferDetailLevel.EXECUTIVE         # layer 0 asks for executive
    assert h.node("N6").reporting_format == TransferDetailLevel.MANAGERIAL        # layer 1 asks for managerial
    assert h.problems() == []


def test_moving_under_a_deeper_node_pushes_the_node_down():
    h = layered_hierarchy()
    h.move_node("N2", "N4")
    assert h.node("N2").layer.value == 3 and h.node("N2").reporting_format == TransferDetailLevel.TECHNICAL_SUMMARY


def test_a_move_is_recorded_with_what_it_changed():
    h = layered_hierarchy()
    h.move_node("N4", "N0")
    event = h.events[-1]
    assert event.name == "NodeMoved"
    details = dict(event.details)
    assert details["layer_shift"] == "-1" and details["moved"] == "N4 N6" and details["reporting_rederived"] == "N4 N6"


@pytest.mark.parametrize("node_id, parent, message", [
    ("N0", "N1", "H02: the root"),
    ("N1", "N1", "under itself"),
    ("N1", "N6", "own descendants"),
    ("N6", "N3", "H10"),
    ("N6", "N4", "already under"),
    ("N9", "N0", "unknown node"),
    ("N2", "N6", "no transfer rule"),
])
def test_a_move_that_breaks_a_rule_is_refused_and_changes_nothing(node_id, parent, message):
    h = layered_hierarchy()
    before, events = h.nodes(), len(h.events)
    with pytest.raises(DomainError, match=message):
        h.move_node(node_id, parent)
    assert h.nodes() == before and len(h.events) == events


def test_without_a_layer_registry_a_move_only_shifts_layers():
    h = bare_hierarchy()
    h.move_node("N4", "N0")
    assert h.node("N4").layer.value == 1 and h.node("N4").reporting_format is None


# --- terminal nodes

def test_a_node_with_children_cannot_become_terminal_H10():
    with pytest.raises(DomainError, match="H10"):
        layered_hierarchy().set_terminal("N1", True)


def test_a_leaf_can_become_terminal_and_open_again_and_the_change_is_recorded_once():
    h = layered_hierarchy()
    h.set_terminal("N6", True)
    h.set_terminal("N6", True)
    assert h.node("N6").is_terminal and [e.name for e in h.events].count("NodeTerminalChanged") == 1
    h.set_terminal("N6", False)
    assert not h.node("N6").is_terminal


def test_a_node_that_became_terminal_cannot_get_a_child_H10():
    h = layered_hierarchy()
    h.set_terminal("N6", True)
    with pytest.raises(DomainError, match="H10"):
        h.add_node(node("N7", 4, "N6"))


# --- node details

def test_a_name_and_a_field_of_activity_can_change():
    h = layered_hierarchy()
    h.change_details("N4", name="Transit Authority", field_of_activity="transit")
    assert (h.node("N4").name, h.node("N4").field_of_activity) == ("Transit Authority", "transit")
    assert dict(h.events[-1].details)["fields"] == "field_of_activity name"


def test_confidentiality_changes_from_text_and_a_bad_value_is_refused():
    h = layered_hierarchy()
    h.change_details("N4", confidentiality="confidential")
    assert h.node("N4").confidentiality == Confidentiality.CONFIDENTIAL
    with pytest.raises(DomainError, match="confidentiality must be one of"):
        h.change_details("N4", confidentiality="secret")


@pytest.mark.parametrize("field", ["node_id", "layer", "parent_id", "is_terminal"])
def test_an_id_a_layer_a_parent_and_the_terminal_flag_do_not_change_here(field):
    with pytest.raises(DomainError, match="cannot be changed here"):
        layered_hierarchy().change_details("N4", **{field: "x"})


def test_a_reporting_format_set_by_a_layer_rule_is_not_changed_on_the_node():
    with pytest.raises(DomainError, match="set by the transfer rule"):
        layered_hierarchy().change_details("N4", reporting_format="executive")
    with pytest.raises(DomainError, match="minimum judge score is set by the transfer rule"):
        layered_hierarchy().change_details("N4", min_judge_score=15)


def test_without_a_layer_registry_the_node_holds_its_own_reporting_values():
    h = bare_hierarchy()
    h.change_details("N1", reporting_format="managerial", min_judge_score=17)
    assert h.node("N1").reporting_format == TransferDetailLevel.MANAGERIAL and h.node("N1").min_judge_score == 17


@pytest.mark.parametrize("changes, message", [({"min_judge_score": 0}, "1 to 20"), ({"min_judge_score": 21}, "1 to 20"),
                                              ({"name": "  "}, "needs a name"), ({"field_of_activity": ""}, "field of activity")])
def test_a_bad_detail_is_refused(changes, message):
    with pytest.raises(DomainError, match=message):
        bare_hierarchy().change_details("N1", **changes)


# --- the layer registry

def test_a_layer_is_defined_once_and_needs_a_name_and_a_real_rule():
    h = layered_hierarchy()
    with pytest.raises(DomainError, match="already defined"):
        h.define_layer(2, "Again")
    with pytest.raises(DomainError, match="needs a name"):
        h.define_layer(5, "  ")
    with pytest.raises(DomainError, match="must be a TransferRule"):
        h.define_layer(5, "Five", rule="executive")


def test_the_rule_for_a_node_is_the_rule_of_its_parents_layer():
    h = layered_hierarchy()
    assert h.receiving_rule("N6").detail_level == TransferDetailLevel.TECHNICAL_SUMMARY
    assert h.receiving_rule("N1").detail_level == TransferDetailLevel.EXECUTIVE
    assert h.receiving_rule("N0") is None and bare_hierarchy().receiving_rule("N1") is None


def test_a_new_node_must_send_what_the_rule_of_its_parents_layer_asks_for():
    h = layered_hierarchy()
    with pytest.raises(DomainError, match="asks for technical_summary"):
        h.add_node(node("N7", 3, "N4", reporting="managerial", score=18))
    with pytest.raises(DomainError, match="minimum judge score"):
        h.add_node(node("N7", 3, "N4", reporting="technical_summary", score=17))
    with pytest.raises(DomainError, match="sends nothing"):
        h.add_node(node("N7", 3, "N4"))
    h.add_node(node("N7", 3, "N4", reporting="technical_summary", score=18))


def test_a_new_node_under_a_layer_with_no_rule_is_refused():
    with pytest.raises(DomainError, match="no transfer rule"):
        layered_hierarchy().add_node(node("N7", 4, "N6", reporting="detailed_technical", score=18))


def test_a_layer_registry_added_after_the_nodes_shows_where_they_disagree():
    h = bare_hierarchy()
    h.change_details("N1", reporting_format="managerial", min_judge_score=18)
    h.define_layer(0, "Top", rule=rule("executive"))
    assert "N1 sends managerial, but the rule of layer 0 asks for executive" in h.problems()
    with pytest.raises(DomainError, match="disagree"):
        h.check_complete()


def test_a_layer_with_nodes_but_no_registry_entry_is_a_problem():
    h = bare_hierarchy()
    h.define_layer(0, "Top", rule=rule("executive"))
    assert "layer 1 has nodes but is not in the layer registry" in h.problems()


def test_a_layer_that_receives_packages_needs_a_rule():
    h = bare_hierarchy()
    h.define_layer(0, "Top")
    assert "layer 0 receives packages from layer 1 but has no transfer rule" in h.problems()


def test_the_rules_ask_for_less_detail_going_up():
    h = Hierarchy()
    h.define_layer(0, "Top", rule=rule("technical_summary"))
    h.define_layer(1, "Middle", rule=rule("executive"))
    assert any("asks for more detail" in p for p in h.problems())


def test_changing_a_layer_rule_updates_the_nodes_that_send_into_it():
    h = layered_hierarchy()
    h.set_layer_rule(1, rule("managerial", score=17))
    assert h.node("N4").min_judge_score == 17 and h.node("N6").min_judge_score == 18
    assert h.events[-1].name == "LayerRuleChanged" and h.problems() == []


def test_a_rule_that_breaks_the_registry_is_refused_and_nothing_changes():
    h = layered_hierarchy()
    before = (h.nodes(), h.layers())
    with pytest.raises(DomainError, match="breaks the layer registry"):
        h.set_layer_rule(2, rule("executive"))          # layer 1 asks for managerial, which is more detail than executive
    with pytest.raises(DomainError, match="breaks the layer registry"):
        h.set_layer_rule(0, None)                       # layer 0 receives packages from layer 1
    assert (h.nodes(), h.layers()) == before


def test_a_rule_cannot_be_set_on_a_layer_that_is_not_defined():
    with pytest.raises(DomainError, match="not defined"):
        layered_hierarchy().set_layer_rule(7, rule("executive"))
