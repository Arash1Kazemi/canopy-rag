from baseline_runner import metrics
from baseline_runner.corpus import load_files, load_questions


def test_the_case_study_loads_as_documented():
    files = load_files()
    assert len(files) == 22
    assert len({f.doc_id for f in files}) == 20
    assert len({f.stem for f in files}) == 22
    assert len(load_questions()) == 26


def test_an_empty_set_has_no_share_and_no_median():
    assert metrics.share([]) is None
    assert metrics.median([None]) is None
    assert metrics.percentile([], 90) is None


def test_share_median_and_percentile():
    assert metrics.share([True, False, True, True]) == 0.75
    assert metrics.median([3, 1, 2]) == 2
    assert metrics.percentile(list(range(1, 11)), 90) == 9   # nearest rank: the 9th of 10 values
    assert metrics.percentile([5], 90) == 5


def test_retrieval_scores_for_a_question_that_needs_two_files():
    groups = [{"D11_a"}, {"D16_b"}]
    hit, precision, recall = metrics.retrieval_scores(["D11_a", "D07_x", "D11_a"], groups)
    assert hit is True
    assert abs(precision - 2 / 3) < 1e-9   # two of the three chunks are from answer-key files
    assert recall == 0.5                   # one of the two answer-key files was found


def test_retrieval_scores_when_nothing_relevant_was_found():
    assert metrics.retrieval_scores(["D07_x"], [{"D11_a"}]) == (False, 0.0, 0.0)
    assert metrics.retrieval_scores([], [{"D11_a"}]) == (False, 0.0, 0.0)


def record(qid, qtype, correct, refused=False, gr4=None, gr5=True, ttft=1.0, wall=2.0, tps=10.0):
    return {"question_id": qid, "type": qtype, "correct": correct, "refused": refused, "GR4": gr4, "GR5": gr5,
            "ttft_s": ttft, "wall_s": wall, "tokens_per_s": tps, "gpu_mb": 1500, "ram_mb": 900}


def test_summary_separates_answerable_from_refusal_questions():
    records = [
        record("Q01", "version_trap", True), record("Q02", "version_trap", False, gr5=False),
        record("Q03", "duplicate", True, gr4=False), record("Q04", "factual", False, refused=True),
        record("Q22", "node_boundary", True), record("Q23", "unanswerable", False),
    ]
    summary = metrics.summarize_answers(records)
    assert summary["M01"] == 0.5            # 2 of the 4 answerable questions
    assert summary["M02"] == 0.75           # GR5 failed once among the 4
    assert summary["M03"] == 0.5            # one of the two refusal questions
    assert summary["M04"] == 0.25           # one false refusal among the 4
    assert summary["M09"] == 0.5            # Q01 right and cited, Q02 not
    assert summary["M12"] == 0.0            # Q03 cited the duplicate twice
    assert summary["M14"] is None           # Q20 and Q21 are not in this set
    assert summary["M25_gpu_mb_max"] == 1500
