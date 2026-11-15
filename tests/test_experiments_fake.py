import csv
import json

from baseline_runner import experiments as ex
from baseline_runner.corpus import read_csv
from baseline_runner.config import JUDGE_PROBE
from baseline_runner.fakes import FakeClient


def context(tmp_path, client=None):
    # test doubles for everything that would touch the machine or print
    return ex.make_context(client or FakeClient(), tmp_path, sampler=lambda: {}, ps=lambda: "", log=lambda *_: None)


def rows_of(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_e1_writes_a_row_per_model_setting_k_and_answerable_question(tmp_path):
    ctx = context(tmp_path)
    summary = ex.run_e1(ctx, ["nomic-embed-text"], chunk_names=("file", "words80"), ks=(1, 3))
    assert len(summary) == 4                                  # 1 model x 2 chunk settings x 2 values of k
    assert len(rows_of(tmp_path / "e1_rows.csv")) == 4 * 23   # 23 answerable questions each
    assert all(0 <= row["M06_hit"] <= 1 and 0 <= row["M08_recall"] <= 1 for row in summary)


def test_more_chunks_never_lower_the_hit_rate(tmp_path):
    summary = ex.run_e1(context(tmp_path), ["nomic-embed-text"], chunk_names=("words80",), ks=(1, 3, 5))
    hits = [row["M06_hit"] for row in sorted(summary, key=lambda r: r["k"])]
    assert hits == sorted(hits)


def test_e2_answers_every_answerable_question_with_the_right_files(tmp_path):
    summary = ex.run_e2(context(tmp_path), ["qwen3-4b"])
    rows = rows_of(tmp_path / "e2_rows.csv")
    assert len(rows) == 23 and {r["type"] for r in rows}.isdisjoint({"unanswerable", "node_boundary"})
    assert summary[0]["M01"] is not None


def test_e3_retrieves_only_inside_the_asking_node(tmp_path):
    # Hard rule H01, end to end: every retrieved file belongs to the node that asked.
    ctx = context(tmp_path)
    ex.run_e3(ctx, ["qwen3-4b"], "nomic-embed-text")
    node_of_stem = {f.stem: f.node_id for f in ctx.files}
    rows = rows_of(tmp_path / "e3_rows.csv")
    assert len(rows) == 26
    for row in rows:
        assert all(node_of_stem[s] == row["asked_at_node"] for s in row["retrieved"].split(";") if s), row["question_id"]


def test_e3_refuses_to_share_a_water_figure_with_the_bus_project(tmp_path):
    ctx = context(tmp_path, FakeClient(reply=lambda prompt, images, json_mode: "Insufficient knowledge."))
    ex.run_e3(ctx, ["qwen3-4b"], "nomic-embed-text")
    q22 = next(r for r in rows_of(tmp_path / "e3_rows.csv") if r["question_id"] == "Q22")
    assert q22["GR2"] == "True" and "D07" not in q22["retrieved"]


def test_a_stub_that_always_refuses_gets_every_refusal_right_and_every_other_answer_wrong(tmp_path):
    ctx = context(tmp_path, FakeClient(reply=lambda prompt, images, json_mode: "Insufficient knowledge."))
    summary = ex.run_e3(ctx, ["qwen3-4b"], "nomic-embed-text")
    assert summary[0]["M03"] == 1.0 and summary[0]["M01"] == 0.0 and summary[0]["M04"] == 1.0


def test_e4_counts_the_facts_found_in_the_text_read_from_the_image(tmp_path):
    image = tmp_path / "page.png"
    image.write_bytes(b"not really a picture")
    perfect = "4 August 8 weeks 310,000 Ali Hosseini 15 July Leila Rahimi 25 July"
    rows = ex.run_e4(context(tmp_path, FakeClient(reply=lambda p, i, j: perfect)), ["qwen3-vl-2b"], [image])
    assert rows[0]["facts_total"] == 7 and rows[0]["M13"] == 1.0
    rows = ex.run_e4(context(tmp_path, FakeClient(reply=lambda p, i, j: "4 August only")), ["glm-ocr-q8"], [image])
    assert rows[0]["facts_found"] == 1 and "310000" in rows[0]["missing"]


def test_the_judge_verdict_is_read_from_json_or_from_loose_text():
    assert ex.parse_verdict('{"verdict": "correct", "reason": "same"}') == "correct"
    assert ex.parse_verdict('Sure! verdict: "wrong" because') == "wrong"
    assert ex.parse_verdict("no idea") == "unparsed"


def test_e5_scores_a_judge_that_always_says_correct_at_one_half(tmp_path):
    ctx = context(tmp_path)
    summary = ex.run_e5(ctx, ["qwen3-4b"], read_csv(JUDGE_PROBE))
    fixed = next(s for s in summary if s["setting"] == "fixed")
    assert fixed["accuracy"] == 0.5 and fixed["M20_repeatability"] == 1.0 and fixed["probes"] == 52


def test_e6_records_one_summary_per_model_and_k(tmp_path):
    summary = ex.run_e6(context(tmp_path), ["qwen3-4b", "phi4-mini"], "nomic-embed-text", ks=(1, 3))
    assert len(summary) == 4
    assert {s["k"] for s in summary} == {1, 3}


def test_meta_records_the_settings_a_result_depends_on(tmp_path):
    ctx = context(tmp_path)
    ex.write_meta(ctx, command="e1", chunks="words80")
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["ollama_version"] == "fake" and meta["chunks"] == "words80"


def test_regrade_changes_only_the_grades_and_keeps_the_original_file(tmp_path):
    ctx = context(tmp_path)
    ex.run_e2(ctx, ["qwen3-4b"])
    before = (tmp_path / "e2_rows.csv").read_text(encoding="utf-8")
    summary = ex.regrade(ctx, tmp_path, "e2")
    assert (tmp_path / "e2_rows.csv").read_text(encoding="utf-8") == before
    regraded = rows_of(tmp_path / "e2_rows_regraded.csv")
    assert len(regraded) == 23 and "was_correct" in regraded[0]
    assert summary[0]["llm"] == "qwen3-4b" and summary[0]["M01"] is not None
