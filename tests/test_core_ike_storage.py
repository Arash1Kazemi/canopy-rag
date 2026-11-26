"""Test area: Phase 9 IKE storage and workflows. The same contract tests run against the in-memory and the SQLite
repository: a group is stored whole or not at all, a duplicate edge is refused, the order is fixed, a node's list holds
only its own edges, and the SQLite file survives a restart."""
import pytest

from issue_builders import CLOCK, city_nodes
from rag_core.ike import EntityRef, IkeRelation, RelationType, relations_from_rows
from rag_core.infrastructure.memory_ike import InMemoryIkeRepository
from rag_core.infrastructure.sqlite_ike import SqliteIkeRepository
from rag_core.workflows.ike import CASE_STUDY, FAILED, IkeService, load_case_study, read_rows

T = RelationType


def seed():
    return relations_from_rows(read_rows(CASE_STUDY / "ike_seed_relations.csv"), CLOCK())


def edge(kind=T.ISSUE_RELATED_TO_KNOWLEDGE, source=("issue", "I02"), target=("knowledge_item", "D11"), node="N6", **f):
    return IkeRelation(relation_type=kind, source=EntityRef(*source), target=EntityRef(*target), node_id=node,
                       created_at=CLOCK(), **f)


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        yield InMemoryIkeRepository()
    else:
        r = SqliteIkeRepository(tmp_path / "ike.sqlite")
        yield r
        r.close()


def test_relations_are_stored_unchanged_in_a_fixed_order(repo):
    assert repo.is_empty()
    relations = seed()
    repo.add_all(reversed(relations))
    assert not repo.is_empty()
    stored = repo.all_relations()
    assert sorted(stored, key=lambda r: r.sort_key) == stored
    assert set(stored) == set(relations)                                  # every field, evidence and basis included
    assert [str(r.node_id) for r in stored][:1] == ["N1"]                   # N1 before N2, N4, N6


def test_a_nodes_list_holds_only_its_own_relations(repo):
    repo.add_all(seed())
    n6 = repo.relations_of_node("N6")
    assert n6 and all(str(r.node_id) == "N6" for r in n6)
    assert [r.relation_type for r in repo.relations_of_node("N4")] == [T.ISSUE_RELATED_TO_KNOWLEDGE, T.EXECUTOR_HAS_EXPERTISE,
                                                                        T.EXECUTOR_HAS_EXPERTISE]
    assert repo.relations_of_node("N3") == []


def test_a_duplicate_edge_is_refused_and_nothing_of_the_group_is_kept(repo):
    repo.add_all([edge()])
    assert repo.contains(edge(evidence="D11")) and not repo.contains(edge(target=("knowledge_item", "D16")))
    with pytest.raises(ValueError):
        repo.add_all([edge(target=("knowledge_item", "D16")), edge(basis="again")])
    assert repo.all_relations() == [edge()]
    with pytest.raises(ValueError):
        repo.add_all([edge(target=("knowledge_item", "D18")), edge(target=("knowledge_item", "D18"))])
    assert len(repo.all_relations()) == 1


def test_similar_in_either_direction_is_one_edge(repo):
    repo.add_all([edge(T.ISSUE_SIMILAR_TO_ISSUE, ("issue", "I04"), ("issue", "I02"))])
    assert repo.contains(edge(T.ISSUE_SIMILAR_TO_ISSUE, ("issue", "I02"), ("issue", "I04")))
    with pytest.raises(ValueError):
        repo.add_all([edge(T.ISSUE_SIMILAR_TO_ISSUE, ("issue", "I02"), ("issue", "I04"))])


def test_relations_survive_a_restart(tmp_path):
    path = tmp_path / "project.sqlite"
    first = SqliteIkeRepository(path)
    first.add_all(seed())
    before = first.all_relations()
    first.close()
    again = SqliteIkeRepository(path)
    assert again.all_relations() == before and len(before) == len(seed())
    again.close()


# --- the workflows ----------------------------------------------------------------------------------------------
def service(repo):
    case = load_case_study()
    return IkeService(repo, city_nodes(), CLOCK, **case.lookups), case


def test_the_seed_is_added_once(repo):
    ike, case = service(repo)
    first = ike.seed(case.seed_rows)
    assert first.ok and first.added == len(case.seed_rows) == 38 and first.skipped == 0
    second = ike.seed(case.seed_rows)
    assert second.ok and (second.added, second.skipped) == (0, 38)
    assert len(repo.all_relations()) == 38


def test_add_relation_reports_a_broken_rule_and_saves_nothing(repo):
    ike, _ = service(repo)
    ok = ike.add_relation("issue_lacks_knowledge", "issue", "I04", "missing_knowledge", "off-peak ridership", "N6")
    assert ok.ok and ok.added == 1
    for bad in [("issue_lacks_knowledge", "issue", "I04", "missing_knowledge", "off-peak ridership", "N6"),   # duplicate
                ("issue_related_to_knowledge", "issue", "I04", "knowledge_item", "D07", "N6"),               # other node
                ("issue_related_to_knowledge", "issue", "I04", "knowledge_item", "D16", "N9"),               # unknown node
                ("executor_has_expertise", "issue", "I04", "expertise", "surveys", "N6")]:                    # wrong kind
        result = ike.add_relation(*bad)
        assert result.outcome == FAILED and result.detail
    assert len(repo.all_relations()) == 1


def test_the_service_summary_is_node_scoped_and_named(repo):
    ike, case = service(repo)
    ike.seed(case.seed_rows)
    s = ike.summary("N6", names=case.names)
    assert s.node_name == "Bus Network Project" and s.issues == ("I01", "I02", "I03", "I04")
    assert s == ike.summary("N6", names=case.names)
    assert [str(r.node_id) for r in ike.relations_of_node("N2")] == ["N2"] * 3
