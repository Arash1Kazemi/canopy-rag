"""The core's test doubles are tested too, so a bug in a double cannot hide a bug in the code (unit-testing rule 3)."""
from rag_core.fakes import FixedClock, SpyRunner, StubVisionModel, stub_page_renderer, stub_pdf_reader


def test_the_fixed_clock_never_moves():
    clock = FixedClock()
    assert clock() == clock() == "2026-11-01T10:00:00Z"


def test_the_stub_lvm_returns_pages_in_order_and_remembers_them():
    lvm = StubVisionModel(["one", "two"])
    assert [lvm.read_page(b"a"), lvm.read_page(b"b")] == ["one", "two"] and lvm.seen == [b"a", b"b"]


def test_the_stub_reader_and_renderer_return_what_they_were_given():
    assert stub_pdf_reader(["p1"])("any.pdf") == ["p1"]
    assert stub_page_renderer(2)("any.pdf") == [b"png-1", b"png-2"]


def test_the_spy_runner_writes_the_converted_file(tmp_path):
    runner = SpyRunner(b"docx bytes")
    runner(["soffice", "--headless", "--convert-to", "docx", "--outdir", str(tmp_path), "C:/x/old.doc"])
    assert (tmp_path / "old.docx").read_bytes() == b"docx bytes" and len(runner.calls) == 1


def test_the_stub_language_model_replies_and_remembers():
    from rag_core.fakes import StubLanguageModel
    model = StubLanguageModel("- a | b")
    assert model.generate("p1") == "- a | b" and model.prompts == ["p1"]
    failing = StubLanguageModel(error=ConnectionError("no server"))
    import pytest
    with pytest.raises(ConnectionError):
        failing.generate("p2")
    assert failing.prompts == ["p2"]
