"""Test area: the `judge` command (Phase 10), with a stub judge. Nothing calls a real model. Exit code 0 is a result (a pass, a fail
or a failed judgment); exit code 2 is a setup problem (Ollama not reachable, a layer that receives nothing, a missing file)."""
import pytest
from baseline_runner.ollama_api import OllamaClient, OllamaError

from core_builders import layered_hierarchy, rule
from judge_builders import reply
from rag_core import cli_judge
from rag_core.__main__ import main
from rag_core.fakes import SequenceLanguageModel
from rag_core.infrastructure.sqlite_judging import SqliteJudgeRepository

TEXT = "The Transit Agency has 135 buses [D10_bus_fleet_inventory_v2]."


@pytest.fixture
def files(tmp_path):
    text = tmp_path / "package.md"
    text.write_text(TEXT, encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("D10 lists 135 buses.", encoding="utf-8")
    return {"text": str(text), "source": str(source), "db": str(tmp_path / "judge.sqlite")}


def use(monkeypatch, *replies):
    model = SequenceLanguageModel(*replies, model_tag="phi4-mini:3.8b")
    monkeypatch.setattr(cli_judge, "make_language_model", lambda args: model)
    return model


def stored(files):
    repo = SqliteJudgeRepository(files["db"])
    try:
        return repo.all_scores()
    finally:
        repo.close()


def run(files, *extra):
    return main(["judge", "--text", files["text"], "--db", files["db"], *extra])


def test_two_identical_runs_pass_and_both_are_stored(files, monkeypatch, capsys):
    use(monkeypatch, reply(19))
    assert run(files, "--layer", "1", "--run-id", "J1") == 0
    out = capsys.readouterr().out
    assert "Repeat 1: PASS  19/20 (threshold 18)" in out and "Repeat 2: PASS  19/20" in out
    assert "Parent organizations" in out and "managerial" in out and "model phi4-mini:3.8b" in out
    assert "same decision: yes" in out and "same total: yes" in out
    assert [(s.run_id, s.repeat, s.outcome, s.total) for s in stored(files)] == [("J1", 1, "pass", 19), ("J1", 2, "pass", 19)]


def test_the_default_is_two_runs_and_one_run_has_no_repeatability_line(files, monkeypatch, capsys):
    model = use(monkeypatch, reply(20))
    assert run(files, "--layer", "0") == 0
    assert len(model.prompts) == 2
    capsys.readouterr()
    files["db"] += ".one"
    assert run(files, "--layer", "0", "--runs", "1") == 0
    assert "Repeatability" not in capsys.readouterr().out


def test_17_fails_and_the_two_runs_disagree(files, monkeypatch, capsys):
    use(monkeypatch, reply(17), reply(18))
    assert run(files, "--layer", "1") == 0
    out = capsys.readouterr().out
    assert "Repeat 1: FAIL  17/20 (threshold 18)" in out and "Repeat 2: PASS  18/20 (threshold 18)" in out
    assert "same decision: no" in out


def test_a_reply_that_cannot_be_read_is_a_failed_judgment_and_never_a_pass(files, monkeypatch, capsys):
    use(monkeypatch, "Score: 20 out of 20")
    assert run(files, "--layer", "1", "--runs", "1") == 0
    out = capsys.readouterr().out
    assert "FAILED JUDGMENT" in out and "not a pass" in out and "PASS" not in out
    assert stored(files)[0].outcome == "invalid"


def test_the_threshold_is_read_from_the_layer_registry(files, monkeypatch, capsys):
    h = layered_hierarchy()
    h.set_layer_rule(1, rule("managerial", score=16))
    monkeypatch.setattr(cli_judge, "load_hierarchy", lambda hierarchy_db: h)
    use(monkeypatch, reply(17))
    assert run(files, "--layer", "1", "--runs", "1") == 0
    assert "Repeat 1: PASS  17/20 (threshold 16)" in capsys.readouterr().out


def test_the_real_layer_registry_gives_18_to_layers_0_1_2(files, monkeypatch, capsys):
    use(monkeypatch, reply(18))
    for layer in ("0", "1", "2"):
        files["db"] = files["db"] + layer
        assert run(files, "--layer", layer, "--runs", "1") == 0
        assert "threshold 18" in capsys.readouterr().out


def test_the_source_and_the_request_go_into_the_prompt(files, monkeypatch):
    model = use(monkeypatch, reply(20))
    assert run(files, "--layer", "1", "--runs", "1", "--source", files["source"], "--request", "Report the fleet size.") == 0
    assert "D10 lists 135 buses." in model.prompts[0] and "Report the fleet size." in model.prompts[0]
    assert stored(files)[0].source_ref == "source.md"


def test_a_layer_that_receives_nothing_exits_2_before_the_model_is_called(files, monkeypatch, capsys):
    model = use(monkeypatch, reply(20))
    assert run(files, "--layer", "3") == 2
    assert "layer 3 receives nothing" in capsys.readouterr().err and model.prompts == [] and stored(files) == []


def test_an_unknown_layer_exits_2(files, monkeypatch, capsys):
    use(monkeypatch, reply(20))
    assert run(files, "--layer", "9") == 2
    assert "not in the registry" in capsys.readouterr().err


def test_a_missing_text_file_exits_2(files, monkeypatch, capsys):
    use(monkeypatch, reply(20))
    files["text"] += ".nope"
    assert run(files, "--layer", "1") == 2
    assert "cannot read" in capsys.readouterr().err


def test_an_empty_text_file_exits_2(files, monkeypatch, capsys):
    use(monkeypatch, reply(20))
    open(files["text"], "w").close()
    assert run(files, "--layer", "1") == 2
    assert "nothing to judge" in capsys.readouterr().err


def test_a_run_id_that_is_stored_exits_2_and_changes_nothing(files, monkeypatch, capsys):
    use(monkeypatch, reply(20))
    assert run(files, "--layer", "1", "--run-id", "J1") == 0
    capsys.readouterr()
    assert run(files, "--layer", "1", "--run-id", "J1") == 2
    assert "already stored" in capsys.readouterr().err and len(stored(files)) == 2


def test_a_model_that_cannot_be_reached_exits_2_and_stores_nothing(files, monkeypatch, capsys):
    use(monkeypatch, OllamaError("cannot reach Ollama at http://127.0.0.1:11500: connection refused"))
    assert run(files, "--layer", "1") == 2
    err = capsys.readouterr().err
    assert "model server" in err and "127.0.0.1:11500" in err and stored(files) == []


def test_with_the_server_down_the_real_adapter_path_exits_2(files, monkeypatch, capsys):
    def down(method, path, payload):
        raise OllamaError("cannot reach Ollama at http://127.0.0.1:11500: connection refused")
    monkeypatch.setattr(cli_judge, "make_client", lambda: OllamaClient(transport=down))
    assert run(files, "--layer", "1") == 2
    assert "model server" in capsys.readouterr().err and stored(files) == []


def test_a_model_that_is_not_pulled_exits_2(files, monkeypatch, capsys):
    transport = lambda method, path, payload: {"version": "0.0"} if path == "/api/version" else {"models": []}
    monkeypatch.setattr(cli_judge, "make_client", lambda: OllamaClient(transport=transport))
    assert run(files, "--layer", "1") == 2
    assert "not downloaded yet" in capsys.readouterr().err


def test_an_unknown_llm_id_exits_2(files, capsys):
    assert run(files, "--layer", "1", "--llm", "no-such-model") == 2
    assert "unknown model id" in capsys.readouterr().err


def test_an_unknown_judge_prompt_exits_2(files, monkeypatch, capsys):
    use(monkeypatch, reply(20))
    assert run(files, "--layer", "1", "--prompt", "P01") == 2
    assert "not for judging" in capsys.readouterr().err
