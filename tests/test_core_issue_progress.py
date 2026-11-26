"""Test area: H07, issue status and progress follow fixed rules. ProgressPercentage from the seven factors of proposal
14.1, with the weights of config/issue_progress_weights.csv (untuned, decision A31)."""
import itertools

import pytest

from issue_builders import issue, weights
from rag_core.infrastructure.issues_csv import load_progress_weights
from rag_core.issues.progress import FACTORS, ProgressPercentage, ProgressWeights, compute_progress, progress_factors
from rag_core.shared.kernel import DomainError


def subs(*statuses, parent="I90"):
    return [issue(f"I{91 + n}", parent_issue_id=parent, position=n + 1, status=s) for n, s in enumerate(statuses)]


def test_the_config_file_has_every_factor_and_adds_up_to_100():
    w = weights()
    assert [name for name, _ in w.weights] == list(FACTORS)
    assert sum(value for _, value in w.weights) == 100


def test_a_new_issue_with_nothing_done_is_at_0():
    assert compute_progress(issue(), [], weights()) == ProgressPercentage(0)


def test_each_factor_adds_its_weight():
    w = weights()
    one = lambda **facts: compute_progress(issue(**facts), [], w).value
    assert one(knowledge_ids=("D10",)) == w.weight("supporting_knowledge")
    assert one(executor_ids=("P01",)) == w.weight("executor_mapped")
    assert one(proposed_solution="Add 6 buses") == w.weight("solution_proposed")
    assert one(research_completed=True) == w.weight("research_completed")
    assert one(review_approved=True) == w.weight("review_approved")
    assert one(proposed_solution="   ") == 0                       # an empty answer is not an answer


def test_sub_issues_count_as_defined_and_as_a_share_solved():
    w = weights()
    # 1 of 4 solved: defined counts fully, solved counts a quarter, rounded down
    got = compute_progress(issue(status="analyzing"), subs("solved", "new", "new", "in_progress"), w)
    assert got.value == int(w.weight("sub_issues_defined") + w.weight("sub_issues_solved") / 4)
    assert progress_factors(issue(), subs("solved", "new"))["sub_issues_solved"] == 0.5


def test_only_direct_sub_issues_count():
    grandchild = issue("I99", parent_issue_id="I91", status="solved", position=9)
    assert compute_progress(issue(), subs("new") + [grandchild], weights()).value == weights().weight("sub_issues_defined")


def test_only_a_solved_issue_shows_100():
    everything = dict(knowledge_ids=("D10",), executor_ids=("P01",), proposed_solution="x", research_completed=True,
                      review_approved=True)
    assert compute_progress(issue(status="analyzing", **everything), subs("solved"), weights()).value == 99
    assert compute_progress(issue(status="solved"), [], weights()).value == 100


def test_h07_the_same_input_gives_the_same_output_in_any_order():
    parent = issue(status="analyzing", knowledge_ids=("D10", "D16"), executor_ids=("P02",))
    children = subs("solved", "new", "in_progress", "solved", "unsolved")
    results = {compute_progress(parent, list(order), weights()) for order in itertools.permutations(children)}
    assert len(results) == 1
    assert compute_progress(parent, children, weights()) == compute_progress(parent, children, load_progress_weights())


def test_h07_status_moves_follow_the_table_every_time():
    for _ in range(3):
        assert issue().with_status("analyzing").status.value == "analyzing"
        with pytest.raises(DomainError):
            issue().with_status("in_progress")


@pytest.mark.parametrize("bad, words", [
    ({**dict.fromkeys(FACTORS, 10), "sub_issues_solved": 40, "review_approved": 20}, "add up to 100"),
    ({name: 0 for name in FACTORS[:-1]}, "exactly the factors"),
    ({**dict.fromkeys(FACTORS, 10), "sub_issues_solved": 40, "review_approved": -0.5}, "whole number"),
])
def test_bad_weights_are_refused(bad, words):
    with pytest.raises(DomainError, match=words):
        ProgressWeights.of(bad)


def test_a_progress_percentage_is_0_to_100():
    for bad in (-1, 101, 50.5, True):
        with pytest.raises(DomainError):
            ProgressPercentage(bad)
    assert str(ProgressPercentage(40)) == "40%"


def test_the_weights_loader_checks_its_columns(tmp_path):
    bad = tmp_path / "w.csv"
    bad.write_text("name,weight\nx,100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columns"):
        load_progress_weights(bad)
