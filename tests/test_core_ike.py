"""Test area: Phase 9 IKE model (proposal 13). The twelve relation types, the kinds each one allows, the rules that
need other relations (duplicates, one node, one parent, no cycle), the case-study seed and the node summary (13.3)."""
import pytest

from issue_builders import CLOCK, city_nodes
from rag_core.ike import (RULES, EntityRef, IkeRelation, RefKind, RelationType, check_relations, derive_relations,
                          relations_from_rows, summarize_node)
from rag_core.ike.model import natural_key, sorted_relations
from rag_core.organization.directory import UnknownNodeError
from rag_core.shared.kernel import DomainError
from rag_core.workflows.ike import CASE_STUDY, load_case_study, read_rows

T = RelationType


def rel(kind, source, target, node="N6", **fields):
    """A relation from short strings such as 'issue:I01' and 'knowledge_item:D11'."""
    s_kind, s_key = source.split(":", 1)
    t_kind, t_key = target.split(":", 1)
    return IkeRelation(relation_type=kind, source=EntityRef(s_kind, s_key), target=EntityRef(t_kind, t_key),
                       node_id=node, created_at=fields.pop("created_at", CLOCK()), **fields)


# --- the twelve types -------------------------------------------------------------------------------------------
def test_there_are_exactly_the_twelve_relation_types_of_proposal_13_1_in_its_order():
    assert [t.value for t in RelationType] == [
        "issue_related_to_knowledge", "issue_depends_on_knowledge", "issue_lacks_knowledge", "issue_similar_to_issue",
        "issue_decomposes_into_issue", "issue_blocked_by_issue", "executor_has_expertise", "executor_worked_on_project",
        "executor_related_to_knowledge", "executor_can_follow_issue", "knowledge_supports_answer",
        "knowledge_limits_or_conflicts_with_answer"]
    assert [t.order for t in RelationType] == list(range(1, 13))
    assert set(RULES) == set(RelationType)
    assert all(t.phrase for t in RelationType)


def test_each_type_goes_from_the_kind_its_sentence_names():
    sides = {t: (s.value, g.value) for t, (s, g) in RULES.items()}
    assert sides[T.ISSUE_LACKS_KNOWLEDGE] == ("issue", "missing_knowledge")
    assert sides[T.EXECUTOR_HAS_EXPERTISE] == ("executor", "expertise")
    assert sides[T.EXECUTOR_WORKED_ON_PROJECT] == ("executor", "project")
    assert sides[T.EXECUTOR_CAN_FOLLOW_ISSUE] == ("executor", "issue")
    assert sides[T.KNOWLEDGE_SUPPORTS_ANSWER] == ("knowledge_item", "answer")
    assert {t for t, s in sides.items() if s[0] == "issue"} == set(list(RelationType)[:6])


@pytest.mark.parametrize("kind,source,target", [
    (T.ISSUE_RELATED_TO_KNOWLEDGE, "executor:P01", "knowledge_item:D11"),
    (T.ISSUE_DEPENDS_ON_KNOWLEDGE, "issue:I01", "issue:I02"),
    (T.EXECUTOR_HAS_EXPERTISE, "executor:P01", "knowledge_item:D11"),
    (T.EXECUTOR_CAN_FOLLOW_ISSUE, "issue:I02", "executor:P03"),          # the wrong way round
    (T.KNOWLEDGE_SUPPORTS_ANSWER, "knowledge_item:D17", "issue:I03"),     # an answer, not the issue itself
    (T.ISSUE_DECOMPOSES_INTO_ISSUE, "issue:I01", "project:BUS"),
])
def test_a_wrong_source_or_target_kind_is_refused(kind, source, target):
    with pytest.raises(DomainError, match="goes from a"):
        rel(kind, source, target)


@pytest.mark.parametrize("kind,key", [("issue", "D11"), ("answer", "P01"), ("knowledge_item", "D 11"),
                                      ("executor", ""), ("expertise", "   "), ("planet", "X1")])
def test_a_bad_reference_is_refused(kind, key):
    with pytest.raises(DomainError):
        EntityRef(kind, key)


def test_an_unknown_relation_type_bad_date_or_bad_evidence_is_refused():
    with pytest.raises(DomainError, match="relation type"):
        rel("issue_owns_issue", "issue:I01", "issue:I02")
    with pytest.raises(DomainError, match="ISO date"):
        rel(T.ISSUE_BLOCKED_BY_ISSUE, "issue:I01", "issue:I02", created_at="yesterday")
    with pytest.raises(DomainError, match="evidence"):
        rel(T.ISSUE_RELATED_TO_KNOWLEDGE, "issue:I01", "knowledge_item:D11", evidence="see the report")


def test_an_issue_is_never_related_to_itself():
    with pytest.raises(DomainError, match="itself"):
        rel(T.ISSUE_SIMILAR_TO_ISSUE, "issue:I02", "issue:I02")


def test_labels_are_normalized_and_similar_has_no_direction():
    assert EntityRef("expertise", "  Route   Planning ").key == "route planning"
    a = rel(T.ISSUE_SIMILAR_TO_ISSUE, "issue:I10", "issue:I2")
    assert (a.source.key, a.target.key) == ("I2", "I10")                  # number order, not text order
    assert a.edge_key == rel(T.ISSUE_SIMILAR_TO_ISSUE, "issue:I2", "issue:I10").edge_key
    assert natural_key("I2") < natural_key("I10")


# --- rules over several relations -------------------------------------------------------------------------------
def test_an_unknown_node_is_refused_through_the_node_directory():
    with pytest.raises(UnknownNodeError):
        check_relations([rel(T.ISSUE_BLOCKED_BY_ISSUE, "issue:I03", "issue:I02", node="N9")], [], city_nodes())


def test_a_duplicate_edge_is_refused_against_stored_and_inside_one_group():
    stored = [rel(T.ISSUE_RELATED_TO_KNOWLEDGE, "issue:I02", "knowledge_item:D11")]
    again = rel(T.ISSUE_RELATED_TO_KNOWLEDGE, "issue:I02", "knowledge_item:D11", evidence="D11", basis="other note")
    with pytest.raises(DomainError, match="duplicate"):
        check_relations([again], stored, city_nodes())
    pair = [rel(T.ISSUE_SIMILAR_TO_ISSUE, "issue:I02", "issue:I04"), rel(T.ISSUE_SIMILAR_TO_ISSUE, "issue:I04", "issue:I02")]
    with pytest.raises(DomainError, match="duplicate"):
        check_relations(pair, [], city_nodes())


def lookups():
    case = load_case_study()
    return case.lookups


def test_issues_and_knowledge_items_stay_in_their_own_node():
    nodes = city_nodes()
    with pytest.raises(DomainError, match="belongs to N2"):     # D07 is the water standard of N2 (the Q22 boundary)
        check_relations([rel(T.ISSUE_RELATED_TO_KNOWLEDGE, "issue:I01", "knowledge_item:D07")], [], nodes, **lookups())
    with pytest.raises(DomainError, match="belongs to N4"):
        check_relations([rel(T.KNOWLEDGE_SUPPORTS_ANSWER, "knowledge_item:D17", "answer:I05")], [], nodes, **lookups())
    with pytest.raises(DomainError, match="does not exist"):
        check_relations([rel(T.ISSUE_BLOCKED_BY_ISSUE, "issue:I03", "issue:I77")], [], nodes, **lookups())
    check_relations([rel(T.KNOWLEDGE_LIMITS_OR_CONFLICTS_WITH_ANSWER, "knowledge_item:D11", "answer:I02")], [], nodes,
                    **lookups())


def test_an_executor_may_appear_in_another_nodes_relation_but_its_own_edges_stay_home():
    nodes = city_nodes()
    check_relations([rel(T.EXECUTOR_RELATED_TO_KNOWLEDGE, "executor:P02", "knowledge_item:D19")], [], nodes, **lookups())
    with pytest.raises(DomainError, match="belongs to N4"):
        check_relations([rel(T.EXECUTOR_HAS_EXPERTISE, "executor:P02", "expertise:bus fleet", node="N6")], [], nodes,
                        **lookups())
    with pytest.raises(DomainError, match="does not exist"):
        check_relations([rel(T.EXECUTOR_CAN_FOLLOW_ISSUE, "executor:P99", "issue:I02")], [], nodes, **lookups())


def test_a_sub_issue_has_one_parent_and_links_never_make_a_cycle():
    nodes = city_nodes()
    stored = [rel(T.ISSUE_DECOMPOSES_INTO_ISSUE, "issue:I01", "issue:I02"),
              rel(T.ISSUE_BLOCKED_BY_ISSUE, "issue:I03", "issue:I02"), rel(T.ISSUE_BLOCKED_BY_ISSUE, "issue:I02", "issue:I04")]
    with pytest.raises(DomainError, match="two parents"):
        check_relations([rel(T.ISSUE_DECOMPOSES_INTO_ISSUE, "issue:I03", "issue:I02")], stored, nodes)
    with pytest.raises(DomainError, match="cycle"):
        check_relations([rel(T.ISSUE_DECOMPOSES_INTO_ISSUE, "issue:I02", "issue:I01")], stored, nodes)
    with pytest.raises(DomainError, match="cycle"):
        check_relations([rel(T.ISSUE_BLOCKED_BY_ISSUE, "issue:I04", "issue:I03")], stored, nodes)
    check_relations([rel(T.ISSUE_BLOCKED_BY_ISSUE, "issue:I04", "issue:I01")], stored, nodes)


# --- the case-study seed ----------------------------------------------------------------------------------------
def seed_relations():
    return relations_from_rows(read_rows(CASE_STUDY / "ike_seed_relations.csv"), CLOCK())


def test_the_seed_passes_every_rule_with_all_lookups():
    check_relations(seed_relations(), [], city_nodes(), **lookups())


def test_every_relation_the_records_state_is_in_the_seed():
    derived = derive_relations(read_rows(CASE_STUDY / "issues.csv"), read_rows(CASE_STUDY / "people.csv"), CLOCK())
    seed = {r.edge_key: r for r in seed_relations()}
    assert len(derived) == 15                                       # I01 -> I02, I03, I04 and 12 expertise labels
    for relation in derived:
        assert seed[relation.edge_key].node_id == relation.node_id


def test_every_seed_relation_that_is_not_a_record_cites_a_case_study_document():
    documents = {r["doc_id"] for r in read_rows(CASE_STUDY / "documents_manifest.csv")}
    for relation in seed_relations():
        assert relation.basis, f"{relation.edge_key} has no basis note"
        if not relation.basis.startswith(("issues.csv", "people.csv")):
            assert relation.evidence in documents


# --- the node summary (13.3) ------------------------------------------------------------------------------------
def summary(node="N6", relations=None):
    case = load_case_study()
    return summarize_node(node, relations if relations is not None else seed_relations(), names=case.names,
                          node_name="Bus Network Project")


def test_the_summary_holds_only_the_nodes_own_relations():
    s = summary("N6")
    assert s.total == sum(1 for r in seed_relations() if str(r.node_id) == "N6") > 0
    assert {e.source_id for e in s.edges} | {e.target_id for e in s.edges} >= {"I01", "P03", "D19"}
    assert not {"I05", "I06", "I07"} & set(s.issues)
    assert all(e.target_id not in ("D06", "D08", "D13", "bus fleet", "leak detection") for e in s.edges)
    assert summary("N4").issues == ("I05",)
    assert dict(summary("N3").counts) == {t.value: 0 for t in RelationType} and summary("N3").edges == ()


def test_the_summary_is_the_same_whatever_order_the_relations_come_in():
    relations = seed_relations()
    forward, backward = summary(relations=relations), summary(relations=list(reversed(relations)))
    assert forward == backward
    assert forward.to_text() == backward.to_text() and forward.edges_csv() == backward.edges_csv()
    assert list(forward.edges) == list(summary(relations=sorted_relations(relations)).edges)


def test_the_summary_answers_the_questions_of_13_3_with_plain_values():
    s = summary()
    data = s.to_dict()
    assert data["issues"] == ["I01", "I02", "I03", "I04"]
    assert data["knowledge_by_issue"]["I02"] == ["D11", "D16"]
    assert data["executors_by_issue"] == {"I02": ["P03"], "I03": ["P01"]}
    assert data["expertise_by_executor"]["P03"] == ["ridership statistics", "survey analysis"]
    assert data["issues_lacking_knowledge"] == {}
    assert list(data["counts"]) == [t.value for t in RelationType] and data["total"] == s.total
    assert all(isinstance(v, (str, int, list, dict)) for v in data.values())


def test_the_summary_text_and_csv_use_readable_names():
    s = summary()
    text = s.to_text()
    assert text.startswith("IKE relation summary for N6 Bus Network Project")
    assert "I01 (Route 7 overcrowded at peak) decomposes into I02 (Verify ridership data)" in text
    assert "P03 (Ali Hosseini, Data analyst) can follow up I02 (Verify ridership data) [D19]" in text
    lines = s.edges_csv().splitlines()
    assert lines[0] == "relation_type,source_kind,source_id,source_name,target_kind,target_id,target_name,evidence,basis"
    assert len(lines) == s.total + 1 and "\r" not in s.edges_csv()
    counts = s.counts_csv().splitlines()
    assert counts[0] == "relation_type,count" and len(counts) == 13
    assert "issue_decomposes_into_issue,3" in counts


def test_a_lacks_knowledge_relation_shows_in_the_summary():
    extra = rel(T.ISSUE_LACKS_KNOWLEDGE, "issue:I04", "missing_knowledge:Off-peak ridership")
    s = summary(relations=seed_relations() + [extra])
    assert s.issues_lacking_knowledge == (("I04", ("off-peak ridership",)),)
    assert "I04 (Re-survey passengers) lacks knowledge about off-peak ridership" in s.to_text()
