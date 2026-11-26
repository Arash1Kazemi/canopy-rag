"""Test area: Phase 7 issues. The Issue entity, the ten statuses (14.1), the node rules, relative position (12.3),
comparison of a draft (12.1, 12.4) and parsing of sub-issue suggestions. Progress (H07) is in test_core_issue_progress.py."""
import pytest

from issue_builders import city_nodes, issue, seed_issues
from rag_core.issues.comparison import IssueDraft, compare_draft, content_words
from rag_core.issues.model import IssueIdentifier
from rag_core.issues.rules import check_issues, next_issue_id, next_position, relative_position, sibling_order
from rag_core.issues.status import ALLOWED_MOVES, IssueStatus, can_move, parse_status
from rag_core.issues.suggestions import SubIssueSuggestion, fill_prompt, parse_suggestions
from rag_core.organization.directory import UnknownNodeError
from rag_core.shared.kernel import DomainError


# --- the Issue entity -----------------------------------------------------------------------------------------------
def test_an_issue_id_is_I_and_digits():
    assert str(IssueIdentifier("I01")) == "I01" and IssueIdentifier("I12").number == 12
    for bad in ("X01", "I", "i01", "I01a", ""):
        with pytest.raises(DomainError, match="issue id"):
            IssueIdentifier(bad)


def test_an_issue_holds_its_metadata():
    i = issue(priority="high", category="capacity", issue_type="question", metadata={"owner": "planning", "area": "east"},
              blocked_by=("I02",), position=3)
    assert (i.priority, i.category, i.issue_type, i.position) == ("high", "capacity", "question", 3)
    assert i.meta == {"area": "east", "owner": "planning"} and i.created_at == "2026-11-25T10:00:00Z"
    assert i.blocked_by == (IssueIdentifier("I02"),) and i.status == IssueStatus.NEW
    assert issue(metadata={"b": "2", "a": "1"}) == issue(metadata={"a": "1", "b": "2"})     # a map, order does not matter


@pytest.mark.parametrize("fields, words", [
    (dict(title="  "), "title"), (dict(description=""), "description"), (dict(field_of_activity=" "), "field of activity"),
    (dict(created_at="yesterday"), "created_at"), (dict(priority="urgent"), "priority"), (dict(issue_type="bug"), "issue_type"),
    (dict(position=0), "position"), (dict(status="done"), "status"), (dict(parent_issue_id="I90"), "own parent"),
    (dict(blocked_by=("I90",)), "blocked by itself"), (dict(blocked_by=("I02", "I02")), "twice"),
])
def test_a_broken_issue_is_refused(fields, words):
    with pytest.raises(DomainError, match=words):
        issue(**fields)


# --- statuses (14.1) and the moves between them (decision A30) ------------------------------------------------------
def test_the_ten_statuses_of_the_proposal():
    assert [s.value for s in IssueStatus] == [
        "new", "analyzing", "knowledge_identified", "executor_identified", "solution_proposed",
        "in_progress", "awaiting_decision", "solved", "unsolved", "archived"]
    assert set(ALLOWED_MOVES) == set(IssueStatus)


def test_the_old_five_values_keep_their_meaning():
    assert parse_status("in progress") == IssueStatus.IN_PROGRESS
    for old in ("new", "analyzing", "solved", "unsolved"):
        assert parse_status(old).value == old


def test_allowed_and_refused_moves():
    i = issue()
    i = i.with_status("analyzing").with_status("knowledge_identified").with_status("solution_proposed")
    i = i.with_status("in_progress").with_status("solved").with_status("archived")
    assert i.status == IssueStatus.ARCHIVED
    with pytest.raises(DomainError, match="H07: an issue cannot move from archived"):
        i.with_status("analyzing")
    with pytest.raises(DomainError, match="from new to solved"):
        issue().with_status("solved")                       # no jumping from new straight to solved
    assert can_move("solved", "analyzing") and not can_move("new", "in_progress")


def test_the_status_never_changes_by_the_back_door():
    with pytest.raises(DomainError, match="with_status"):
        issue().with_changes(status="solved")


# --- the seed issues --------------------------------------------------------------------------------------------------
def test_the_seven_seed_issues_load_without_changing_ids_parents_or_meaning():
    issues = {str(i.issue_id): i for i in seed_issues()}
    assert sorted(issues) == [f"I0{n}" for n in range(1, 8)]
    assert {k: str(i.node_id) for k, i in issues.items()} == {
        "I01": "N6", "I02": "N6", "I03": "N6", "I04": "N6", "I05": "N4", "I06": "N1", "I07": "N2"}
    assert [str(i.parent_issue_id) for k, i in sorted(issues.items()) if i.parent_issue_id] == ["I01", "I01", "I01"]
    assert issues["I01"].title == "Route 7 overcrowded at peak"
    assert issues["I02"].status == IssueStatus.IN_PROGRESS and issues["I02"].meta["status_in_source"] == "in progress"
    assert issues["I03"].status == IssueStatus.SOLVED and issues["I06"].status == IssueStatus.UNSOLVED
    assert [issues[k].position for k in ("I02", "I03", "I04")] == [1, 2, 3]       # the order of the file
    assert issues["I01"].field_of_activity == city_nodes().require("N6").field_of_activity
    check_issues(list(issues.values()), [], city_nodes())                          # every rule holds


# --- node rules -------------------------------------------------------------------------------------------------------
def test_the_node_must_exist():
    with pytest.raises(UnknownNodeError):
        check_issues([issue(node="N99")], [], city_nodes())


def test_a_sub_issue_stays_in_its_parents_node():
    with pytest.raises(DomainError, match="stays in its parent's node"):
        check_issues([issue("I90", node="N4", parent_issue_id="I01")], seed_issues(), city_nodes())
    with pytest.raises(DomainError, match="parent I77 does not exist"):
        check_issues([issue("I90", parent_issue_id="I77")], seed_issues(), city_nodes())


def test_a_blocked_by_link_stays_in_one_node_and_points_at_a_real_issue():
    with pytest.raises(DomainError, match="inside one node"):
        check_issues([issue("I90", blocked_by=("I05",))], seed_issues(), city_nodes())       # I05 is in N4
    with pytest.raises(DomainError, match="I77 does not exist"):
        check_issues([issue("I90", blocked_by=("I77",))], seed_issues(), city_nodes())


def test_no_cycle_in_blocked_by_links():
    issues = seed_issues()
    i02 = next(i for i in issues if str(i.issue_id) == "I02").with_blocker("I04")
    i04 = next(i for i in issues if str(i.issue_id) == "I04").with_blocker("I03")
    check_issues([i02, i04], issues, city_nodes())                        # I02 -> I04 -> I03: a chain is fine
    i03 = next(i for i in issues if str(i.issue_id) == "I03").with_blocker("I02")
    with pytest.raises(DomainError, match="cycle"):
        check_issues([i02, i04, i03], issues, city_nodes())               # ... -> I03 -> I02: back to the start


def test_no_cycle_in_parent_links():
    a = issue("I90", parent_issue_id="I91")
    b = issue("I91", parent_issue_id="I90", position=2)
    with pytest.raises(DomainError, match="cycle"):
        check_issues([a, b], [], city_nodes())


def test_siblings_have_different_positions():
    with pytest.raises(DomainError, match="position 2 is already taken by its sibling I03"):
        check_issues([issue("I90", parent_issue_id="I01", position=2)], seed_issues(), city_nodes())
    assert next_position(IssueIdentifier("I01"), city_nodes().require("N6").node_id, seed_issues()) == 4
    assert str(next_issue_id(seed_issues())) == "I08"


# --- relative position (12.3) -----------------------------------------------------------------------------------------
def test_relative_position_of_a_sub_issue():
    issues = seed_issues()
    i04 = next(i for i in issues if str(i.issue_id) == "I04")
    issues = [i if i is not i04 else i04.with_blocker("I02").with_changes(category="data") for i in issues]
    issues = [i.with_changes(category="data") if str(i.issue_id) == "I02" else i for i in issues]
    where = relative_position("I04", issues)
    assert str(where.parent_id) == "I01" and where.position == 3
    assert [str(x) for x in where.siblings] == ["I02", "I03"]
    assert [str(x) for x in where.blocked_by] == ["I02"] and where.blocks == ()
    assert [str(x) for x in where.same_category] == ["I02"]
    assert [str(x) for x in relative_position("I02", issues).blocks] == ["I04"]
    assert [str(x) for x in relative_position("I01", issues).children] == ["I02", "I03", "I04"]


def test_sibling_order_is_by_position_then_id():
    a, b, c = issue("I93", position=2), issue("I91", position=1), issue("I92", position=2)
    assert [str(i.issue_id) for i in sibling_order([a, b, c])] == ["I91", "I92", "I93"]


# --- comparison of a draft (12.1, 12.4, decision A34) -----------------------------------------------------------------
ROUTE_7_DRAFT = IssueDraft("N6", "Crowding on Route 7 at peak", "Peak load on Route 7 is too high for passengers")


def test_a_draft_about_route_7_crowding_ranks_I01_first():
    matches = compare_draft(ROUTE_7_DRAFT, seed_issues())
    assert str(matches[0].issue_id) == "I01"
    assert set(matches[0].shared_words) == {"7", "load", "peak", "route"}
    assert matches[0].score > matches[1].score and 0 < matches[0].score <= 1
    assert [m.score for m in matches] == sorted((m.score for m in matches), reverse=True)


def test_an_issue_from_another_node_is_never_compared():
    twin = issue("I95", node="N4", title=ROUTE_7_DRAFT.title, description=ROUTE_7_DRAFT.description)   # same words, N4
    matches = compare_draft(ROUTE_7_DRAFT, seed_issues() + [twin])
    assert "I95" not in {str(m.issue_id) for m in matches}
    assert all(str(m.issue_id) in {"I01", "I02", "I03", "I04"} for m in matches)
    assert compare_draft(IssueDraft("N4", "Bus maintenance backlog"), seed_issues())[0].issue_id == IssueIdentifier("I05")


def test_stopwords_are_removed_and_numbers_kept():
    assert content_words("The load on the Route 7 is above the limit") == {"load", "route", "7", "above", "limit"}
    only_stopwords = IssueDraft("N6", "The and of on", "is it the")
    assert compare_draft(only_stopwords, seed_issues()) == []


def test_the_embedding_slot_reranks_but_keeps_the_shared_words():
    def favours_i04(draft_text, issue_text):            # a stand-in for the Phase 8 embedding similarity
        return 0.9 if "survey" in issue_text.lower() else 0.1
    matches = compare_draft(ROUTE_7_DRAFT, seed_issues(), similarity=favours_i04)
    assert str(matches[0].issue_id) in {"I02", "I04"} and matches[0].score == 0.9
    i01 = next(m for m in matches if str(m.issue_id) == "I01")
    assert i01.score == 0.1 and i01.word_score > 0 and "route" in i01.shared_words


def test_comparison_gives_the_same_ranking_on_every_run():
    issues = seed_issues()
    assert compare_draft(ROUTE_7_DRAFT, issues) == compare_draft(ROUTE_7_DRAFT, list(reversed(issues)))


# --- sub-issue suggestions (12.1 step 7) ------------------------------------------------------------------------------
def test_parse_the_models_reply():
    reply = """Here are some ideas:
- Check ridership data | Compare tap-in data with the survey
2. Add buses at peak: Pilot extra buses on Route 7
* Check ridership data | a repeat is kept once

- Ask drivers"""
    got = parse_suggestions(reply)
    assert [s.title for s in got] == ["Check ridership data", "Add buses at peak", "Ask drivers"]   # intro skipped, repeat once
    assert got[0].description == "Compare tap-in data with the survey"
    assert got[1].description == "Pilot extra buses on Route 7"
    assert next(s for s in got if s.title == "Ask drivers").description == "Ask drivers"
    assert parse_suggestions("") == [] and parse_suggestions("\n  \n") == []


def test_a_suggestion_can_be_edited_but_never_empty():
    s = SubIssueSuggestion("Check data", "Compare  two   sources")
    assert s.description == "Compare two sources"
    assert s.edited(title="Verify ridership data").title == "Verify ridership data"
    with pytest.raises(DomainError):
        SubIssueSuggestion(" ", "x")


def test_fill_prompt_needs_every_blank():
    assert fill_prompt("Issue: {{title}} in {{field}}", title="T", field="transport") == "Issue: T in transport"
    with pytest.raises(DomainError, match="blanks"):
        fill_prompt("Issue: {{title}}", title="T", description="extra")
