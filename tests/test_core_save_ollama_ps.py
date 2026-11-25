"""scripts/save_ollama_ps.py: the snapshot file, the sampling and the missing-program case. No real ollama or nvidia-smi runs."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "scripts"))

import save_ollama_ps as sp  # noqa: E402


class FakeRunner:
    """Answers each command from a table and records every command it was asked to run."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, command, timeout=30):
        self.calls.append(list(command))
        return self.answers.get(command[0], (None, "not available: missing"))


MOMENT = datetime(2026, 11, 25, 9, 30, 15, tzinfo=timezone.utc)


def test_snapshot_file_name_has_utc_stamp_and_both_outputs(tmp_path):
    runner = FakeRunner({"ollama": (0, "NAME  PROCESSOR\nqwen3-embedding  100% GPU"),
                         "nvidia-smi": (0, "GPU 0: RTX 3050 Laptop, 2100 MiB")})
    path = sp.take_snapshot(tmp_path / "run1", "ollama", runner=runner, now=lambda: MOMENT)
    assert path.name == "ollama_ps_20261125T093015Z.txt"
    text = path.read_text(encoding="utf-8")
    assert "UTC time: 2026-11-25 09:30:15" in text
    assert "== ollama ps ==" in text and "100% GPU" in text
    assert "== nvidia-smi ==" in text and "2100 MiB" in text
    assert runner.calls == [["ollama", "ps"], ["nvidia-smi"]]


def test_missing_nvidia_smi_is_noted_and_does_not_stop_the_snapshot(tmp_path):
    runner = FakeRunner({"ollama": (0, "NAME  PROCESSOR\nmodel  100% GPU")})
    path = sp.take_snapshot(tmp_path, "ollama", runner=runner, now=lambda: MOMENT)
    text = path.read_text(encoding="utf-8")
    assert "100% GPU" in text
    assert "== nvidia-smi ==" in text
    assert "not available" in text
    assert "exit code: none" in text


def test_missing_ollama_is_noted_too(tmp_path):
    runner = FakeRunner({"nvidia-smi": (0, "GPU ok")})
    path = sp.take_snapshot(tmp_path, "C:/no/such/ollama.exe", runner=runner, now=lambda: MOMENT)
    text = path.read_text(encoding="utf-8")
    assert "GPU ok" in text
    assert "== ollama ps ==" in text


def test_real_run_command_reports_a_missing_program_without_raising():
    code, text = sp.run_command(["program-that-does-not-exist-for-tests-xyz"])
    assert code is None
    assert "not available" in text


def test_two_snapshots_in_the_same_second_get_different_files(tmp_path):
    runner = FakeRunner({"ollama": (0, "a"), "nvidia-smi": (0, "b")})
    first = sp.take_snapshot(tmp_path, "ollama", runner=runner, now=lambda: MOMENT)
    second = sp.take_snapshot(tmp_path, "ollama", runner=runner, now=lambda: MOMENT)
    assert first != second
    assert second.name == "ollama_ps_20261125T093015Z_2.txt"


def test_sampling_takes_count_snapshots_and_sleeps_between_them(tmp_path):
    runner = FakeRunner({"ollama": (0, "a"), "nvidia-smi": (0, "b")})
    sleeps = []
    code = sp.main(["--out", str(tmp_path), "--every", "30", "--count", "3", "--ollama", "ollama"],
                   runner=runner, sleep=sleeps.append, now=lambda: MOMENT)
    assert code == 0
    assert sleeps == [30.0, 30.0]
    assert len(list(tmp_path.glob("ollama_ps_*.txt"))) == 3


def test_one_snapshot_by_default_and_no_sleep(tmp_path):
    runner = FakeRunner({"ollama": (0, "a"), "nvidia-smi": (0, "b")})
    sleeps = []
    sp.main(["--out", str(tmp_path / "e3-first")], runner=runner, sleep=sleeps.append, now=lambda: MOMENT)
    assert sleeps == []
    assert len(list((tmp_path / "e3-first").glob("ollama_ps_*.txt"))) == 1


def test_ollama_program_comes_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_EXE", "E:/tools/ollama.exe")
    assert sp.parse(["--out", str(tmp_path)]).ollama == "E:/tools/ollama.exe"


@pytest.mark.parametrize("argv", [
    ["--out", "x", "--count", "0"],
    ["--out", "x", "--count", "3"],
    ["--out", "x", "--count", "3", "--every", "0"],
])
def test_bad_sampling_options_are_refused(argv):
    with pytest.raises(SystemExit):
        sp.parse(argv)


def test_out_folder_is_required():
    with pytest.raises(SystemExit):
        sp.parse([])
