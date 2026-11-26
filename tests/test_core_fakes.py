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


def test_the_hashing_embedder_is_deterministic_and_records_its_calls():
    from rag_core.fakes import HashingEmbedder
    embedder = HashingEmbedder(dims=16)
    first = embedder.embed(["135 buses", "chlorine"])
    assert first == HashingEmbedder(dims=16).embed(["135 buses", "chlorine"])
    assert len(first[0]) == 16 and abs(sum(x * x for x in first[0]) - 1) < 1e-9
    assert embedder.embed_query("135 buses") == first[0]
    assert embedder.batches == [2] and embedder.queries == ["135 buses"]
    assert HashingEmbedder().embed([""]) == [[0.0] * 64]


def test_the_sequence_model_returns_replies_in_order_then_repeats_the_last_one():
    from rag_core.fakes import SequenceLanguageModel
    model = SequenceLanguageModel("a", "b", model_tag="x")
    assert [model.generate("p1"), model.generate("p2"), model.generate("p3")] == ["a", "b", "b"]
    assert model.prompts == ["p1", "p2", "p3"] and model.model_tag == "x"


def test_the_sequence_model_raises_a_reply_that_is_an_error():
    import pytest
    from rag_core.fakes import SequenceLanguageModel
    model = SequenceLanguageModel("a", ConnectionError("no server"))
    assert model.generate("p") == "a"
    with pytest.raises(ConnectionError):
        model.generate("p")
