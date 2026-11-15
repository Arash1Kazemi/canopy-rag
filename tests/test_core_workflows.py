"""Test area: Registry and layers (H02, H10), Phase 6: the node and layer workflows, and their commands."""
import pytest

from core_builders import layered_hierarchy, rule, version
from rag_core.__main__ import main
from rag_core.infrastructure.memory import InMemoryHierarchyRepository, InMemoryKnowledgeRepository
from rag_core.infrastructure.sqlite import SqliteKnowledgeRepository
from rag_core.infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from rag_core.knowledge.model import KnowledgeItem
from rag_core.shared.kernel import TransferDetailLevel
from rag_core.workflows.organization import FAILED, NODE_DEFINED, NODE_MOVED, OrganizationService


def knowledge():
    """N6 has two documents, N1 has one."""
    repo = InMemoryKnowledgeRepository()
    for item_id, node_id in (("D90", "N6"), ("D91", "N6"), ("D92", "N1")):
        repo.save(KnowledgeItem.register(item_id, node_id, version("1", f"text of {item_id}", item=item_id, node_id=node_id)))
    return repo


@pytest.fixture
def stored(tmp_path):
    repo = SqliteHierarchyRepository(tmp_path / "hierarchy.sqlite")
    repo.save(layered_hierarchy())
    yield repo
    repo.close()


@pytest.fixture
def service(stored):
    return OrganizationService(stored, knowledge())


def unchanged(stored, action):
    before = stored.load().nodes()
    result = action()
    assert not result.ok and stored.load().nodes() == before
    return result


# --- define a node

def test_a_new_node_takes_its_layer_from_its_parent_and_its_rule_from_the_layer_above(service, stored):
    result = service.define_node("N7", "Depot Upgrade", "N4", "depots")
    assert result.outcome == NODE_DEFINED and "layer 3 under N4" in result.detail and "from the rule of layer 2" in result.detail
    n7 = stored.load().node("N7")
    assert n7.layer.value == 3 and n7.reporting_format == TransferDetailLevel.TECHNICAL_SUMMARY and n7.min_judge_score == 18


def test_a_node_cannot_be_given_a_layer_only_a_parent(service):
    import inspect
    assert "layer" not in inspect.signature(service.define_node).parameters


@pytest.mark.parametrize("arguments, message", [
    (dict(node_id="N7", name="x", parent_id="N99", field_of_activity="y"), "unknown node"),
    (dict(node_id="N7", name="x", parent_id="N3", field_of_activity="y"), "H10"),
    (dict(node_id="N4", name="x", parent_id="N1", field_of_activity="y"), "already exists"),
    (dict(node_id="N7", name="x", parent_id="N4", field_of_activity="y", reporting_format="executive"), "asks for technical_summary"),
    (dict(node_id="N7", name="x", parent_id="N4", field_of_activity="y", confidentiality="secret"), "confidentiality must be one of"),
    (dict(node_id="N 7", name="x", parent_id="N4", field_of_activity="y"), "node id uses"),
    (dict(node_id="N7", name="x", parent_id="N6", field_of_activity="y"), "no transfer rule: give"),
    (dict(node_id="N7", name="x", parent_id="N6", field_of_activity="y", reporting_format="detailed_technical",
          min_judge_score=18), "has no transfer rule, so a node under N6"),
])
def test_a_node_that_breaks_a_rule_is_refused_with_the_reason_and_nothing_is_saved(service, stored, arguments, message):
    result = unchanged(stored, lambda: service.define_node(**arguments))
    assert result.outcome == FAILED and message in result.detail


def test_without_a_layer_registry_a_new_node_must_say_what_it_sends(tmp_path):
    from core_builders import node
    from rag_core.organization.model import Hierarchy
    bare = Hierarchy()
    bare.add_node(node("N0", 0))
    s = OrganizationService(InMemoryHierarchyRepository(bare))
    assert "give reporting_format and min_judge_score" in s.define_node("N1", "One", "N0", "x").detail
    assert s.define_node("N1", "One", "N0", "x", reporting_format="executive", min_judge_score=18).ok


# --- move a node

def test_a_move_is_saved_and_says_what_changed(service, stored):
    result = service.move_node("N6", "N2")
    assert result.outcome == NODE_MOVED and "N6: layer 3 -> 2, now sends managerial instead of technical_summary" in result.detail
    assert str(stored.load().parent("N6").node_id) == "N2"


def test_a_move_under_a_terminal_node_is_refused_and_nothing_is_saved(service, stored):
    assert "H10" in unchanged(stored, lambda: service.move_node("N6", "N3")).detail


# --- terminal nodes: both halves of H10

def test_a_node_with_children_cannot_become_terminal(service, stored):
    assert "has children" in unchanged(stored, lambda: service.set_terminal("N1")).detail


def test_a_node_with_two_documents_cannot_become_terminal(service, stored):
    assert "has 2 knowledge items" in unchanged(stored, lambda: service.set_terminal("N6")).detail


def test_the_document_check_needs_the_knowledge_repository(stored):
    assert "give the knowledge database" in unchanged(stored, lambda: OrganizationService(stored).set_terminal("N6")).detail


def test_a_node_with_one_document_and_no_children_can_become_terminal_and_open_again(service, stored):
    service.define_node("N7", "Depot", "N4", "depots")
    service.knowledge.save(KnowledgeItem.register("D93", "N7", version("1", "summary", item="D93", node_id="N7")))
    assert service.set_terminal("N7").ok and stored.load().node("N7").is_terminal
    assert service.set_terminal("N7", is_terminal=False).ok and not stored.load().node("N7").is_terminal


# --- node details and layers

def test_a_name_changes_and_a_rule_owned_value_does_not(service, stored):
    assert service.change_node("N4", name="Transit Authority").ok and stored.load().node("N4").name == "Transit Authority"
    assert "set by the transfer rule" in unchanged(stored, lambda: service.change_node("N4", reporting_format="executive")).detail


def test_an_id_cannot_be_changed_even_when_it_is_asked_for_by_name(service, stored):
    assert "cannot be changed here" in unchanged(stored, lambda: service.change_node("N4", node_id="N9")).detail


def test_a_layer_can_be_added_once(service, stored):
    assert service.define_layer(4, "Internal knowledge sources", "Libraries and archives").ok
    assert stored.load().layer_definition(4).name == "Internal knowledge sources"
    assert "already defined" in service.define_layer(4, "Again").detail


def test_changing_a_layer_rule_updates_the_nodes_that_send_into_it(service, stored):
    result = service.set_layer_rule(1, rule("managerial", score=17))
    assert result.ok and result.node_ids == ("N4",) and stored.load().node("N4").min_judge_score == 17


def test_a_layer_rule_that_breaks_the_registry_is_refused_and_nothing_is_saved(service, stored):
    assert "breaks the layer registry" in unchanged(stored, lambda: service.set_layer_rule(2, rule("executive"))).detail


def test_a_workflow_never_raises_for_a_broken_rule(service):
    assert service.move_node("N9", "N0").outcome == FAILED and service.set_terminal("N9").outcome == FAILED


# --- the commands

def run(capsys, *arguments):
    code = main(list(arguments))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_show_hierarchy_prints_the_layers_the_nodes_and_what_is_not_decided(capsys):
    code, out, _ = run(capsys, "show-hierarchy")
    assert code == 0 and "Layer 0: Strategic layer" in out and "N6 Bus Network Project (bus routes), layer 3" in out
    assert "not decided yet: excluded topics, required fields, output format, maximum length, citation level" in out
    assert out.rstrip().endswith("Problems: none")


def test_the_commands_define_move_and_show_a_changed_hierarchy(capsys, tmp_path):
    db = str(tmp_path / "h.sqlite")
    assert run(capsys, "init-hierarchy", "--db", db)[0] == 0
    code, out, _ = run(capsys, "define-node", "--db", db, "--id", "N7", "--name", "Depot Upgrade", "--parent", "N4", "--field", "depots")
    assert code == 0 and out.startswith("node defined: N7 is in layer 3 under N4")
    code, out, _ = run(capsys, "move-node", "--db", db, "--id", "N6", "--parent", "N5")
    assert code == 1 and out.startswith("failed: H10")
    assert run(capsys, "move-node", "--db", db, "--id", "N6", "--parent", "N2")[0] == 0
    out = run(capsys, "show-hierarchy", "--db", db)[1]
    assert "      N7 Depot Upgrade (depots), layer 3" in out                                   # under N4, which is under N1
    assert "    N6 Bus Network Project (bus routes), layer 2: sends managerial, judge >= 18" in out   # now under N2
    assert "      N6 Bus Network Project" not in out                                        # no longer in layer 3


def test_a_database_that_was_not_started_is_reported_and_not_overwritten(capsys, tmp_path):
    db = str(tmp_path / "h.sqlite")
    code, _, err = run(capsys, "define-node", "--db", db, "--id", "N7", "--name", "x", "--parent", "N4", "--field", "y")
    assert code == 2 and "run init-hierarchy first" in err
    assert run(capsys, "init-hierarchy", "--db", db)[0] == 0
    code, _, err = run(capsys, "init-hierarchy", "--db", db)
    assert code == 2 and "already has nodes" in err


def test_set_terminal_checks_the_documents_in_the_knowledge_database(capsys, tmp_path):
    db, kdb = str(tmp_path / "h.sqlite"), str(tmp_path / "k.sqlite")
    run(capsys, "init-hierarchy", "--db", db)
    code, out, _ = run(capsys, "set-terminal", "--db", db, "--id", "N6")
    assert code == 1 and "give the knowledge database" in out
    k = SqliteKnowledgeRepository(kdb)
    k.save(KnowledgeItem.register("D90", "N6", version("1", "one summary", item="D90", node_id="N6")))
    k.close()
    code, out, _ = run(capsys, "set-terminal", "--db", db, "--id", "N6", "--knowledge-db", kdb)
    assert code == 0 and "N6 is now a terminal node" in out
    assert run(capsys, "set-terminal", "--db", db, "--id", "N6", "--off")[0] == 0
