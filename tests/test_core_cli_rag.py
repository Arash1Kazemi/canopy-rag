"""Test area: the commands `index`, `ask` and `evaluate` (Phase 8D). Fakes only: no model, no network.

The commands build their models in `make_embedder`, `make_language_model`, `make_client` and `server_info`; the tests
replace those functions, as the issue-command tests do. Pinned: exit code 0 for a result (a refusal included), exit code 2
when the setup cannot work (Ollama unreachable, a model not pulled, no index, a stale index, an unknown node, an address
that is not this machine), and no overwriting of an earlier run.
"""
import csv
import json

import pytest

from baseline_runner.fakes import FakeClient
from baseline_runner.ollama_api import OllamaClient, OllamaError
from rag_core import cli_rag
from rag_core.__main__ import main
from rag_core.fakes import HashingEmbedder, StubLanguageModel


def question_text(question_id):
    with open("case_study/answer_key.csv", encoding="utf-8", newline="") as handle:
        return next(r for r in csv.DictReader(handle) if r["question_id"] == question_id)["question"]


@pytest.fixture
def indexed(tmp_path):
    db = tmp_path / "rag.sqlite"
    assert main(["index", "--db", str(db), "--fake-models"]) == 0
    return str(db)


class UnreachableEmbedder:
    """An adapter whose server is down: what OllamaEmbeddingModel does when nothing listens on 127.0.0.1:11500."""
    model_tag = "fake-hash-64"

    def embed(self, texts):
        raise OllamaError("cannot reach Ollama at http://127.0.0.1:11500: connection refused")

    embed_query = embed


class UnreachableLanguageModel:
    def generate(self, prompt):
        raise OllamaError("cannot reach Ollama at http://127.0.0.1:11500: connection refused")


def down_transport(method, path, payload):
    raise OllamaError("cannot reach Ollama at http://127.0.0.1:11500: connection refused")


# ------------------------------------------------------------------ index
def test_index_ingests_then_embeds_and_a_second_run_embeds_nothing(tmp_path, capsys):
    db = str(tmp_path / "rag.sqlite")
    assert main(["index", "--db", db, "--fake-models"]) == 0
    first = capsys.readouterr().out
    assert "ingested the case study" in first and "33 chunks of active versions: 33 embedded now" in first
    assert main(["index", "--db", db, "--fake-models"]) == 0
    second = capsys.readouterr().out
    assert "nothing was ingested" in second and "0 embedded now" in second and "33 already indexed" in second


def test_index_rebuilds_when_the_embedding_model_changes(indexed, monkeypatch, capsys):
    capsys.readouterr()
    monkeypatch.setattr(cli_rag, "make_embedder", lambda args: HashingEmbedder(dims=32, model_tag="fake-hash-32"))
    assert main(["index", "--db", indexed, "--fake-models"]) == 0
    assert "index rebuilt" in capsys.readouterr().out


def test_index_with_the_server_down_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_rag, "make_embedder", lambda args: UnreachableEmbedder())
    assert main(["index", "--db", str(tmp_path / "rag.sqlite"), "--fake-models"]) == 2
    assert "model server" in capsys.readouterr().err


# ------------------------------------------------------------------ ask
def test_ask_q22_at_n6_is_refused_and_prints_the_reason(indexed, monkeypatch, capsys):
    stub = StubLanguageModel("Insufficient knowledge.")
    monkeypatch.setattr(cli_rag, "make_language_model", lambda args: stub)
    capsys.readouterr()
    assert main(["ask", "--db", indexed, "--fake-models", "--node", "N6", question_text("Q22"), "--k", "5"]) == 0
    out = capsys.readouterr().out
    assert "Refused: yes, because the model said it does not have the knowledge" in out
    assert "D07_" not in out and "D08_" not in out                       # nothing of N2 was retrieved
    assert "chlorine" not in stub.prompts[0].split("Question:")[0].lower()


def test_ask_d10_prints_135_with_a_checked_citation_and_its_chunk(indexed, monkeypatch, capsys):
    stub = StubLanguageModel("The Transit Agency has 135 buses [D10_bus_fleet_inventory_v2].")
    monkeypatch.setattr(cli_rag, "make_language_model", lambda args: stub)
    capsys.readouterr()
    assert main(["ask", "--db", indexed, "--fake-models", "--node", "N4", question_text("Q01"), "--k", "5", "--prompt", "P13"]) == 0
    out = capsys.readouterr().out
    assert "135 buses" in out and "prompt P13 (version 2)" in out
    assert "Citations (checked against the chunks that were given):" in out
    assert "[D10_bus_fleet_inventory_v2" in out and "chunk D10@2#" in out
    assert "D10_bus_fleet_inventory_v1" not in out and "120" not in stub.prompts[0]


def test_ask_removes_and_reports_a_citation_the_model_invented(indexed, monkeypatch, capsys):
    monkeypatch.setattr(cli_rag, "make_language_model",
                        lambda args: StubLanguageModel("135 buses [D10_bus_fleet_inventory_v2] and [D99_invented]."))
    capsys.readouterr()
    assert main(["ask", "--db", indexed, "--fake-models", "--node", "N4", question_text("Q01"), "--k", "5"]) == 0
    out = capsys.readouterr().out
    assert "removed from the answer, not in the context: D99_invented" in out


def test_ask_prints_the_pages_of_a_citation(capsys):
    from types import SimpleNamespace
    from rag_core.rag.answering import Answer
    from rag_core.rag.citation import Citation
    citation = Citation("D19_meeting_minutes_2025-06-18", "D19@1#1", 1, 2, ("Minutes", "Decisions"))
    answer = Answer("Route 7 was chosen [D19_meeting_minutes_2025-06-18].", False, "", (citation,), (), False, "P01", 1,
                    ("D19@1#1",), (), True, "raw", 100, 10)
    cli_rag.print_result(SimpleNamespace(question="q?", node_id="N6", k=3, hits=(), answer=answer))
    out = capsys.readouterr().out
    assert "[D19_meeting_minutes_2025-06-18, pp. 1-2, Minutes > Decisions, chunk D19@1#1]" in out


def test_ask_without_an_index_exits_2(tmp_path, capsys):
    assert main(["ask", "--db", str(tmp_path / "none.sqlite"), "--fake-models", "--node", "N6", "q?"]) == 2
    assert "run `python -m rag_core index" in capsys.readouterr().err


def test_ask_an_unknown_node_exits_2_before_any_model_call(indexed, monkeypatch, capsys):
    stub = StubLanguageModel("x")
    monkeypatch.setattr(cli_rag, "make_language_model", lambda args: stub)
    assert main(["ask", "--db", indexed, "--fake-models", "--node", "N99", "q?"]) == 2
    assert "unknown node" in capsys.readouterr().err and stub.prompts == []


def test_ask_on_an_index_made_by_another_model_exits_2(indexed, monkeypatch, capsys):
    monkeypatch.setattr(cli_rag, "make_embedder", lambda args: HashingEmbedder(dims=32, model_tag="fake-hash-32"))
    assert main(["ask", "--db", indexed, "--fake-models", "--node", "N6", "q?"]) == 2
    assert "index the knowledge again" in capsys.readouterr().err


def test_ask_with_the_embedding_server_down_exits_2(indexed, monkeypatch, capsys):
    monkeypatch.setattr(cli_rag, "make_embedder", lambda args: UnreachableEmbedder())
    assert main(["ask", "--db", indexed, "--fake-models", "--node", "N6", "q?"]) == 2
    assert "Ollama" in capsys.readouterr().err


def test_ask_with_the_language_model_down_exits_2(indexed, monkeypatch, capsys):
    monkeypatch.setattr(cli_rag, "make_language_model", lambda args: UnreachableLanguageModel())
    assert main(["ask", "--db", indexed, "--fake-models", "--node", "N6", question_text("Q06")]) == 2
    assert "model server" in capsys.readouterr().err


# ------------------------------------------------------------------ evaluate
def test_evaluate_runs_end_to_end_with_fakes_and_writes_the_baseline_format(tmp_path, capsys):
    out = tmp_path / "run"
    assert main(["evaluate", "--fake-models", "--out", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == {"e3_rows.csv", "e3_summary.csv", "comparison.csv", "comparison.md", "meta.json", "knowledge.sqlite"}
    with (out / "e3_rows.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 26
    baseline_columns = next(csv.reader((cli_rag.RESULTS / "e3-first" / "e3_rows.csv").open(encoding="utf-8", newline="")))
    assert list(rows[0])[:len(baseline_columns)] == baseline_columns            # the same columns in the same order, then extras
    assert list(rows[0])[len(baseline_columns):] == ["prompt", "refusal_reason", "invalid_citations", "chunk_ids_used", "chunk_ids_omitted"]
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["engine"] == "core" and meta["prompt"] == "P01 v1" and meta["k"] == 3 and meta["embedding"] == "qwen3-embedding-0.6b"
    shown = capsys.readouterr().out
    assert "M01" in shown and "M05" in shown and "not measured" in shown          # missing metrics are said, not hidden
    assert "\r" not in (out / "e3_rows.csv").read_text(encoding="utf-8")        # LF line endings


def test_evaluate_will_not_overwrite_an_earlier_run(tmp_path, capsys):
    out = str(tmp_path / "run")
    assert main(["evaluate", "--fake-models", "--out", out, "--questions", "Q22"]) == 0
    assert main(["evaluate", "--fake-models", "--out", out, "--questions", "Q22"]) == 2
    assert "already holds a run" in capsys.readouterr().err


def test_evaluate_with_a_refusing_model_refuses_everything_and_grades_it(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_rag, "make_language_model", lambda args: StubLanguageModel("Insufficient knowledge."))
    out = tmp_path / "run"
    assert main(["evaluate", "--fake-models", "--out", str(out)]) == 0
    with (out / "e3_summary.csv").open(encoding="utf-8", newline="") as handle:
        (summary,) = list(csv.DictReader(handle))
    assert float(summary["M03"]) == 1.0 and float(summary["M01"]) == 0.0 and float(summary["M04"]) == 1.0


def test_evaluate_with_ollama_unreachable_exits_2_and_writes_no_result(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_rag, "make_client", lambda: OllamaClient(transport=down_transport))
    out = tmp_path / "run"
    assert main(["evaluate", "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert "cannot be used" in err and "--fake-models" in err
    assert not (out / "e3_rows.csv").exists()


def test_evaluate_with_a_model_that_is_not_pulled_exits_2(tmp_path, monkeypatch, capsys):
    class Server(FakeClient):
        def models(self):
            return {"qwen3-embedding:0.6b": "digest"}          # phi4-mini is missing

    monkeypatch.setattr(cli_rag, "make_client", lambda: Server())
    assert main(["evaluate", "--out", str(tmp_path / "run")]) == 2
    assert "not downloaded yet: phi4-mini:3.8b" in capsys.readouterr().err


def test_a_server_that_is_not_this_machine_is_refused(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("RAG_OLLAMA_URL", "http://10.0.0.5:11500")
    assert main(["evaluate", "--out", str(tmp_path / "run")]) == 2
    assert "H06" in capsys.readouterr().err


def test_evaluate_with_the_real_adapters_over_a_fake_server_records_timings(tmp_path, monkeypatch, capsys):
    """OllamaEmbeddingModel and OllamaLanguageModel on top of a fake client: the real wiring, the timings and the pull check."""
    class Server(FakeClient):
        def models(self):
            return {"qwen3-embedding:0.6b": "d1", "phi4-mini:3.8b": "d2"}

    server = Server()
    monkeypatch.setattr(cli_rag, "make_client", lambda: server)
    monkeypatch.setattr(cli_rag, "sampler_and_ps", lambda args: (lambda: {"gpu_mb": 3000, "ram_mb": 40}, lambda: "NAME phi4-mini 100% GPU"))
    out = tmp_path / "run"
    assert main(["evaluate", "--out", str(out), "--questions", "Q01,Q06,Q22"]) == 0
    with (out / "e3_rows.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["question_id"] for r in rows] == ["Q01", "Q06", "Q22"]
    assert all(float(r["tokens_per_s"]) > 0 and r["gpu_mb"] == "3000" for r in rows)
    models_used = {call[1] for call in server.calls}
    assert models_used == {"qwen3-embedding:0.6b", "phi4-mini:3.8b"}
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["ollama_version"] == "fake" and "phi4-mini" in meta["ollama_ps"]
    chats = [call for call in server.calls if call[0] == "chat"]
    assert all("Documents:" in call[2] for call in chats)       # the Phase 2 prompt P01 went to the model
