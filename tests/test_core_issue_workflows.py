"""Test area: Phase 7 issue workflows and commands. Use cases get their repository, node directory, clock, weights and
language model as arguments; tests pass test doubles (StubLanguageModel, FixedClock) and never need a running model."""
import csv

import pytest

from issue_builders import CLOCK, PROJECT, city_nodes, seed_issues, weights
from rag_core import __main__ as cli
from rag_core import cli_issues
from rag_core.fakes import StubLanguageModel
from rag_core.infrastructure.memory import InMemoryIssueRepository
from rag_core.infrastructure.sqlite_issues import SqliteIssueRepository
from rag_core.issues.suggestions import SubIssueSuggestion
from rag_core.workflows.issues import FAILED, IssueService

PROMPT = (PROJECT / "prompts" / "suggest_sub_issues_v1.txt").read_text(encoding="utf-8")
REPLY = """- Check the ridership numbers | Compare tap-in counts with the passenger survey
- Run a pilot with extra buses | Add buses on Route 7 at peak for a few weeks
- Survey more passengers | Ask off-peak travellers too"""


@pytest.fixture(params=["memory", "sqlite"])
def service(request, tmp_path):
    if request.param == "memory":
        repo = InMemoryIssueRepository(seed_issues())
    else:
        repo = SqliteIssueRepository(tmp_path / "issues.sqlite")
        repo.add_all(seed_issues())
    yield IssueService(repo, city_nodes(), CLOCK, weights())
    if request.param == "sqlite":
        repo.close()


# --- create an issue (12.1) -------------------------------------------------------------------------------------------
def test_create_an_issue_with_metadata(service):
    result = service.create_issue("N6", "Bus stops on Route 7 have no shelter", "Riders wait in the rain",
                                  priority="medium", category="stops", metadata={"reported_by": "survey"})
    assert result.ok and result.issue_ids == ("I08",)
    new = service.repo.get("I08")
    assert (str(new.node_id), new.priority, new.category, new.meta) == ("N6", "medium", "stops", {"reported_by": "survey"})
    assert new.created_at == CLOCK() and new.field_of_activity == city_nodes().require("N6").field_of_activity
    assert new.position == 2 and new.status.value == "new"                  # after I01 among the roots of N6


def test_create_a_sub_issue_takes_the_next_position(service):
    result = service.create_issue("N6", "Count boardings by hand", "A one-day manual count", parent_id="I01")
    assert result.ok and service.repo.get("I08").position == 4
    assert [str(x) for x in service.position("I01").children] == ["I02", "I03", "I04", "I08"]


@pytest.mark.parametrize("call, words", [
    (dict(node_id="N99"), "unknown node"),
    (dict(node_id="N4", parent_id="I01"), "stays in its parent's node"),
    (dict(node_id="N6", blocked_by=("I05",)), "inside one node"),
    (dict(node_id="N6", priority="urgent"), "priority"),
])
def test_create_refuses_a_broken_issue_and_saves_nothing(service, call, words):
    call = dict(call)
    node_id = call.pop("node_id")
    result = service.create_issue(node_id, "A title", "A description", **call)
    assert result.outcome == FAILED and words in result.detail
    assert len(service.repo.all_issues()) == 7


# --- status and dependencies ------------------------------------------------------------------------------------------
def test_set_status_follows_the_table(service):
    assert service.set_status("I04", "analyzing").ok
    refused = service.set_status("I04", "archived")
    assert refused.ok                                                       # analyzing -> archived is allowed
    again = service.set_status("I04", "analyzing")
    assert again.outcome == FAILED and "H07" in again.detail
    assert service.repo.get("I04").status.value == "archived"


def test_a_blocker_that_closes_a_cycle_is_refused(service):
    assert service.add_blocker("I04", "I02").ok
    result = service.add_blocker("I02", "I04")
    assert result.outcome == FAILED and "cycle" in result.detail
    assert service.repo.get("I02").blocked_by == ()


def test_progress_reads_the_stored_sub_issues(service):
    # I01 has three sub-issues, one solved (I03): defined counts fully, solved counts a third
    w = weights()
    assert service.progress("I01").value == int(w.weight("sub_issues_defined") + w.weight("sub_issues_solved") / 3)
    assert service.progress("I03").value == 100                             # solved


# --- comparison -------------------------------------------------------------------------------------------------------
def test_compare_a_route_7_draft(service):
    result = service.compare("N6", "Crowding on Route 7 at peak", "Peak load on Route 7 is too high for passengers")
    assert result.ok and str(result.matches[0].issue_id) == "I01"
    assert {str(m.node_id) for m in [service.repo.get(m.issue_id) for m in result.matches]} == {"N6"}
    assert service.compare("N99", "x").outcome == FAILED


# --- sub-issue suggestions: suggest, then a person accepts, edits or rejects ------------------------------------------
def test_suggest_uses_the_versioned_prompt_and_saves_nothing(service):
    model = StubLanguageModel(REPLY)
    result = service.suggest_sub_issues("I01", model, PROMPT)
    assert result.ok and len(result.suggestions) == 3
    assert "Route 7 overcrowded at peak" in model.prompts[0] and "{{" not in model.prompts[0]
    assert "Verify ridership data" not in model.prompts[0]                 # the known sub-issues are never shown (M15)
    assert len(service.repo.all_issues()) == 7


def test_accept_one_edit_one_reject_one_saves_two_together(service):
    first, second, third = service.suggest_sub_issues("I01", StubLanguageModel(REPLY), PROMPT).suggestions
    chosen = [first, second.edited(title="Pilot six extra buses on Route 7")]          # the third is rejected
    result = service.accept_sub_issues("I01", chosen)
    assert result.ok and result.issue_ids == ("I08", "I09")
    saved = [service.repo.get(i) for i in result.issue_ids]
    assert [s.title for s in saved] == ["Check the ridership numbers", "Pilot six extra buses on Route 7"]
    assert all(str(s.parent_issue_id) == "I01" and str(s.node_id) == "N6" for s in saved)
    assert [s.position for s in saved] == [4, 5] and saved[0].meta["source"].startswith("sub-issue suggestion")


def test_accepting_nothing_saves_nothing(service):
    assert service.accept_sub_issues("I01", []).outcome == FAILED
    assert len(service.repo.all_issues()) == 7


def test_a_failure_while_saving_keeps_none_of_the_group(tmp_path, monkeypatch):
    repo = SqliteIssueRepository(tmp_path / "issues.sqlite")
    repo.add_all(seed_issues())
    service = IssueService(repo, city_nodes(), CLOCK, weights())
    real_insert, calls = repo._insert, []

    def fail_on_second(row):
        calls.append(row)
        if len(calls) == 2:
            raise __import__("sqlite3").IntegrityError("simulated failure")
        real_insert(row)
    monkeypatch.setattr(repo, "_insert", fail_on_second)
    chosen = [SubIssueSuggestion("One", "first"), SubIssueSuggestion("Two", "second")]
    result = service.accept_sub_issues("I01", chosen)
    assert result.outcome == FAILED and "nothing was saved" in result.detail
    assert len(repo.all_issues()) == 7
    repo.close()


def test_an_unreachable_model_fails_politely(service):
    result = service.suggest_sub_issues("I01", StubLanguageModel(error=ConnectionError("refused")), PROMPT)
    assert result.outcome == FAILED and "could not answer" in result.detail and "11500" in result.detail


def test_a_reply_with_no_suggestion_fails(service):
    result = service.suggest_sub_issues("I01", StubLanguageModel("Sorry, I cannot help with that:"), PROMPT)
    assert result.outcome == FAILED and "no suggestion" in result.detail


# --- the commands (python -m rag_core ...) ----------------------------------------------------------------------------
@pytest.fixture
def db(tmp_path):
    path = tmp_path / "project.sqlite"
    assert cli.main(["migrate-db", "--db", str(path)]) == 0
    return str(path)


def test_list_and_show_the_seed_issues(db, capsys):
    capsys.readouterr()
    assert cli.main(["list-issues", "--db", db, "--node", "N6"]) == 0
    out = capsys.readouterr().out
    assert "1. I01 [analyzing" in out and "  3. I04 [new" in out and "I05" not in out
    assert cli.main(["show-issue", "--db", db, "--id", "I01"]) == 0
    out = capsys.readouterr().out
    assert "progress (H07)" in out and "I02, I03, I04" in out and "sub_issues_solved" in out


def test_create_issue_survives_a_new_process(db, capsys):
    assert cli.main(["create-issue", "--db", db, "--node", "N6", "--title", "Night buses on Route 7",
                     "--description", "No service after 23:00", "--priority", "low", "--meta", "source=council"]) == 0
    assert "I08 is a new issue in N6" in capsys.readouterr().out
    assert cli.main(["show-issue", "--db", db, "--id", "I08"]) == 0      # a new repository on the same file
    out = capsys.readouterr().out
    assert "Night buses on Route 7" in out and "source=council" in out
    assert cli.main(["create-issue", "--db", db, "--node", "N4", "--parent", "I01", "--title", "x", "--description", "y"]) == 1


def test_compare_issue_and_set_status_commands(db, capsys):
    assert cli.main(["compare-issue", "--db", db, "--node", "N6", "--title", "Crowding on Route 7 at peak"]) == 0
    assert "1. I01" in capsys.readouterr().out
    assert cli.main(["set-issue-status", "--db", db, "--id", "I04", "--status", "solved"]) == 1
    assert cli.main(["set-issue-status", "--db", db, "--id", "I04", "--status", "analyzing"]) == 0


def test_suggest_then_accept_from_the_saved_file(db, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli_issues, "make_language_model", lambda tag: StubLanguageModel(REPLY))
    out = tmp_path / "m15_I01_suggestions.csv"
    assert cli.main(["suggest-sub-issues", "--db", db, "--issue", "I01", "--out", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8", newline="")))
    assert [r["number"] for r in rows] == ["1", "2", "3"] and all(r["matches_known_sub_issue"] == "" for r in rows)
    assert rows[0]["prompt"] == "P12 suggest_sub_issues_v1.txt" and b"\r\n" not in out.read_bytes()
    capsys.readouterr()
    assert cli.main(["accept-sub-issues", "--db", db, "--issue", "I01", "--from", str(out), "--take", "1,3"]) == 0
    assert "I08, I09" in capsys.readouterr().out
    assert cli.main(["accept-sub-issues", "--db", db, "--issue", "I01", "--from", str(out), "--take", "7"]) == 1


def test_suggest_without_a_model_fails_politely(db, capsys):
    # the real adapter: the unit-test fixture blocks every connection, so the model cannot be reached
    assert cli.main(["suggest-sub-issues", "--db", db, "--issue", "I01"]) == 2
    err = capsys.readouterr().err
    assert "could not answer" in err and "Traceback" not in err


def test_an_empty_database_asks_for_migrate(tmp_path, capsys):
    assert cli.main(["list-issues", "--db", str(tmp_path / "new.sqlite"), "--node", "N6"]) == 2
    assert "migrate-db" in capsys.readouterr().err
