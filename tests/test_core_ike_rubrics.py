"""Test area: Phase 9 human rubrics for M15 and M16. The score sheets list exactly the issues their metric names, with
the titles of case_study/issues.csv, and start empty (no score and no target is written in advance)."""
from pathlib import Path

from rag_core.workflows.ike import CASE_STUDY, read_rows

RUBRICS = Path(__file__).resolve().parent.parent / "metrics" / "rubrics"


def issues():
    return {r["issue_id"]: r for r in read_rows(CASE_STUDY / "issues.csv")}


def test_the_m15_sheet_lists_the_known_sub_issues_of_i01_unscored():
    rows = read_rows(RUBRICS / "m15_score_sheet.csv")
    known = [i for i, r in issues().items() if r["parent_issue_id"] == "I01"]
    assert [r["sub_issue_id"] for r in rows] == known == ["I02", "I03", "I04"]
    assert all(r["title"] == issues()[r["sub_issue_id"]]["title"] for r in rows)
    assert all(r["found"] == "" and r["matching_suggestions"] == "" for r in rows)


def test_the_m16_sheet_lists_every_issue_in_its_node_unscored():
    rows = read_rows(RUBRICS / "m16_score_sheet.csv")
    assert [r["issue_id"] for r in rows] == list(issues()) == [f"I0{n}" for n in range(1, 8)]
    for row in rows:
        assert (row["node_id"], row["issue_title"]) == (issues()[row["issue_id"]]["node_id"], issues()[row["issue_id"]]["title"])
        assert row["rating"] == ""


def test_both_rubrics_exist_and_set_no_target():
    for name in ("m15_sub_issue_recall.md", "m16_solution_usefulness.md"):
        text = (RUBRICS / name).read_text(encoding="utf-8")
        assert "No target" in text and "to agree with supervisor" in text
    assert "1 to 5" in (RUBRICS / "m16_solution_usefulness.md").read_text(encoding="utf-8")
