"""Test area: the Phase 8D evaluation harness and `baseline_runner e3 --engine core` (no model, no network).

Pinned: the core run uses the Phase 2 grading and the Phase 2 file format; the comparison table says "not measured" for a
number that is missing; the baseline numbers come from results/e3-first and, without that folder, from metrics/metrics.csv;
and the Phase 2 runner can hand retrieval and answering to the core without changing its default engine.
"""
import csv

import pytest

from baseline_runner import experiments as ex
from baseline_runner.__main__ import main as baseline_main
from baseline_runner.fakes import FakeClient
from rag_core.evaluation import NOT_MEASURED, compare, load_baseline


def rows_of(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ the baseline numbers
def test_the_saved_baseline_run_gives_the_numbers_of_metrics_csv():
    baseline = load_baseline("results/e3-first", "phi4-mini")
    assert baseline["M01"] == pytest.approx(0.913, abs=0.001)         # the regraded run, as metrics/metrics.csv says
    assert baseline["M02"] == pytest.approx(0.87, abs=0.001) and baseline["M03"] == 1.0 and baseline["M09"] == 1.0
    assert baseline["M24_median"] == pytest.approx(0.704, abs=0.001) and baseline["M24_p90"] == pytest.approx(1.52, abs=0.001)
    assert baseline["M06"] == 1.0 and baseline["M08"] == 1.0 and 0.5 < baseline["M07"] < 0.6
    assert "M05" not in baseline                                      # never measured: the judge comes in Phase 10


def test_without_the_saved_run_the_baseline_column_of_metrics_csv_is_used(tmp_path):
    baseline = load_baseline(tmp_path / "missing", "phi4-mini")
    assert baseline["M01"] == 0.913 and baseline["M24_median"] == 0.70 and baseline["M24_p90"] == 1.52
    assert baseline["M22"] == 0.21 and baseline["M23"] == 37.5 and "M05" not in baseline


def test_an_unknown_model_has_no_saved_baseline_but_still_the_metrics_csv_numbers(tmp_path):
    assert load_baseline("results/e3-first", "no-such-model")["M01"] == 0.913


# ------------------------------------------------------------------ the comparison table
def test_compare_marks_missing_numbers_and_reads_the_direction_of_each_metric():
    summary = {"M01": 0.8, "M04": 0.1, "M22": None, "M09": 1.0}
    baseline = {"M01": 0.9, "M04": 0.0, "M22": 0.2, "M09": 1.0}
    rows = {r["metric"]: r for r in compare(summary, baseline)}
    assert rows["M01"]["verdict"] == "worse" and rows["M01"]["change"] == -0.1       # higher is better, and it fell
    assert rows["M04"]["verdict"] == "worse"                                          # false refusal: lower is better, and it rose
    assert rows["M09"]["verdict"] == "same"
    assert rows["M22"]["core"] == NOT_MEASURED and rows["M22"]["verdict"] == "not comparable"
    assert rows["M05"]["baseline"] == NOT_MEASURED and rows["M05"]["core"] == NOT_MEASURED
    assert [r["metric"] for r in compare({}, {})] == ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09", "M22", "M23",
                                                      "M24 median", "M24 p90"]


# ------------------------------------------------------------------ the Phase 2 runner with --engine core
def context(tmp_path):
    return ex.make_context(FakeClient(), tmp_path, sampler=lambda: {}, ps=lambda: "", log=lambda *_: None)


def test_e3_with_the_core_engine_writes_the_baseline_files_and_stays_inside_the_node(tmp_path):
    ctx = context(tmp_path)
    summary = ex.run_e3(ctx, ["qwen3-4b"], "nomic-embed-text", engine="core")
    rows = rows_of(tmp_path / "e3_rows.csv")
    assert len(rows) == 26 and len(rows_of(tmp_path / "e3_summary.csv")) == 1 == len(summary)
    node_of_stem = {f.stem: f.node_id for f in ctx.files}
    for row in rows:
        assert all(node_of_stem[s] == row["asked_at_node"] for s in row["retrieved"].split(";") if s), row["question_id"]
        assert row["prompt"] == "P01"
    assert not any("D10_bus_fleet_inventory_v1" in row["retrieved"] or "_copy" in row["retrieved"] for row in rows)   # active versions only
    assert summary[0]["M22"] is not None and summary[0]["M06"] is not None


def test_the_default_engine_is_still_the_phase_2_code(tmp_path):
    ctx = context(tmp_path)
    ex.run_e3(ctx, ["qwen3-4b"], "nomic-embed-text")
    rows = rows_of(tmp_path / "e3_rows.csv")
    assert "prompt" not in rows[0] and len(rows) == 26             # the baseline columns, no core extras


def test_the_core_engine_needs_a_core_chunking_policy(tmp_path):
    with pytest.raises(ValueError, match="core's policies"):
        ex.run_e3(context(tmp_path), ["qwen3-4b"], "nomic-embed-text", chunk_name="file", engine="core")
    with pytest.raises(ValueError, match="engine is one of"):
        ex.run_e3(context(tmp_path), ["qwen3-4b"], "nomic-embed-text", engine="other")


def test_the_runner_option_engine_core_is_e3_only_and_defaults_to_baseline(tmp_path, capsys):
    assert baseline_main(["e3", "--fake", "--models", "phi4-mini", "--out", str(tmp_path / "a"), "--engine", "core",
                          "--embedding", "nomic-embed-text"]) == 0
    assert "prompt" in rows_of(tmp_path / "a" / "e3_rows.csv")[0]
    assert baseline_main(["e3", "--fake", "--models", "phi4-mini", "--out", str(tmp_path / "b"), "--embedding", "nomic-embed-text"]) == 0
    assert "prompt" not in rows_of(tmp_path / "b" / "e3_rows.csv")[0]
    with pytest.raises(SystemExit):
        baseline_main(["e6", "--fake", "--engine", "core", "--embedding", "nomic-embed-text", "--out", str(tmp_path / "c")])
    with pytest.raises(SystemExit):
        baseline_main(["e3", "--fake", "--engine", "core", "--chunks", "file", "--embedding", "nomic-embed-text", "--out", str(tmp_path / "d")])


def test_a_core_run_can_be_regraded_by_the_phase_2_command(tmp_path):
    ex.run_e3(context(tmp_path), ["qwen3-4b"], "nomic-embed-text", engine="core")
    assert baseline_main(["regrade", "--run-id", "x", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "e3_rows_regraded.csv").is_file()           # the extra columns pass through the regrade
