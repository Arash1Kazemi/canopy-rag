from baseline_runner import grading
from baseline_runner.corpus import load_files, load_questions, read_csv
from baseline_runner.config import JUDGE_PROBE

QUESTIONS = {q["question_id"]: q for q in load_questions()}
FACTS = grading.load_key_facts()
TYPE_RULES = grading.load_type_rules()
STEMS = [f.stem for f in load_files()]
REFUSAL_TYPES = {"unanswerable", "node_boundary"}


def grade(qid, answer):
    return grading.grade_answer(QUESTIONS[qid], FACTS[qid], answer, TYPE_RULES, STEMS)


def test_thousands_separators_are_removed_before_comparing():
    assert grading.normalize("8,200 Households") == "8200 households"
    assert grading.normalize("12,000 EUR") == "12000 eur"


def test_every_expected_answer_passes_its_own_fact_rule():
    # The expected answer is what a perfect system would say, so it must pass GR1 and GR3.
    # Refusal questions are skipped: their expected answers explain what must not leak.
    for qid, q in QUESTIONS.items():
        if q["type"] in REFUSAL_TYPES:
            assert grading.says_refusal(q["expected_answer"]), qid
            continue
        results, _ = grade(qid, q["expected_answer"])
        for rule in ("GR1", "GR3"):
            assert results.get(rule, True), f"{qid} fails {rule}"


def test_every_question_has_key_facts_and_a_type_rule():
    assert set(FACTS) == set(QUESTIONS)
    assert {q["type"] for q in QUESTIONS.values()} <= set(TYPE_RULES)


def test_judge_probe_right_answers_pass_and_wrong_answers_fail():
    # A wrong answer that passes is a known blind spot of string matching, and the probe file says so.
    for probe in read_csv(JUDGE_PROBE):
        results, _ = grade(probe["question_id"], probe["candidate"])
        passed = all(results[rule] for rule in ("GR1", "GR2", "GR3") if rule in results)
        if probe["label"] == "right":
            assert passed, f"{probe['probe_id']} should pass"
        elif probe["gr1_blind_spot"] == "yes":
            assert passed, f"{probe['probe_id']} is a blind spot and should pass the string rule"
        else:
            assert not passed, f"{probe['probe_id']} should fail"


def test_a_refusal_that_leaks_a_forbidden_fact_fails():
    leaky = "Insufficient knowledge, but the usual value is 0.2 mg/L."
    assert grade("Q22", leaky)[0]["GR2"] is False
    assert grade("Q22", "Insufficient knowledge.")[0]["GR2"] is True


def test_a_guess_instead_of_a_refusal_fails():
    assert grade("Q23", "The metro budget is 1.2 billion EUR.")[0]["GR2"] is False


def test_the_conflict_answer_needs_both_routes_and_a_conflict_word():
    both = "The sources disagree: Route 12 says one thing and Route 7 another."
    assert grade("Q06", both)[0]["GR3"] is True
    assert grade("Q06", "Route 12 is the busiest route.")[0]["GR3"] is False
    assert grade("Q06", "Route 12 and Route 7 are both busy.")[0]["GR3"] is False


def test_citations_are_read_from_square_brackets():
    answer = "135 buses [D10_bus_fleet_inventory_v2.md] and more [D13_maintenance_schedule_2025, D12_driver_shift_rules]. [note]"
    assert grading.parse_citations(answer) == [
        "D10_bus_fleet_inventory_v2", "D13_maintenance_schedule_2025", "D12_driver_shift_rules"]


def test_an_old_version_is_not_an_answer_key_source_for_the_current_figure():
    groups = grading.gold_groups(QUESTIONS["Q01"]["source_files"], STEMS)
    assert grading.citations_valid(["D10_bus_fleet_inventory_v2"], groups) is True
    assert grading.citations_valid(["D10_bus_fleet_inventory_v1"], groups) is False


def test_a_citation_from_another_node_is_outside_the_sources():
    groups = grading.gold_groups(QUESTIONS["Q14"]["source_files"], STEMS)
    assert grading.citations_valid(["D01_budget_summary_2025"], groups) is True
    assert grading.citations_valid(["D01_budget_summary_2025", "D07_water_quality_standards"], groups) is False


def test_no_citation_at_all_is_not_valid():
    groups = grading.gold_groups(QUESTIONS["Q14"]["source_files"], STEMS)
    assert grading.citations_valid([], groups) is False


def test_a_bare_document_id_accepts_every_file_of_that_document():
    groups = grading.gold_groups("D11, D16", STEMS)
    assert len(groups) == 2
    assert groups[0] == {"D11_ridership_report_H1_2025"}


def test_the_duplicate_question_accepts_the_copy_as_a_source():
    groups = grading.gold_groups(QUESTIONS["Q03"]["source_files"], STEMS)
    assert groups == [{"D12_driver_shift_rules", "D12_driver_shift_rules_copy"}]


def test_citing_the_file_and_its_copy_fails_the_cite_once_rule():
    one = ["D12_driver_shift_rules"]
    both = ["D12_driver_shift_rules", "D12_driver_shift_rules_copy"]
    assert grading.duplicate_cited_once(one) is True
    assert grading.duplicate_cited_once(both) is False
    assert grading.duplicate_cited_once([]) is False


def test_citations_do_not_decide_whether_an_answer_is_correct():
    assert grading.is_correct({"GR1": True, "GR5": False}) is True
    assert grading.is_correct({"GR1": False, "GR5": True}) is False
    assert grading.is_correct({"GR1": True, "GR4": False, "GR5": True}) is False
