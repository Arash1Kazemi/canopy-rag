"""Test area: Chunking. No text is lost, the size limit holds, the overlap is as set, and every chunk knows its source."""
import re

import pytest

from baseline_runner.chunking import words_windows
from baseline_runner.corpus import load_files
from rag_core.ingestion.extractors import MarkdownExtractor, pages_to_document
from rag_core.knowledge.chunking import POLICIES, ChunkingPolicy, Section, chunk_text, window_starts
from rag_core.knowledge.model import DocumentFormat, KnowledgeItemId, VersionTag
from rag_core.shared.kernel import DomainError

IDS = dict(item_id=KnowledgeItemId("D90"), version_tag=VersionTag("1"), node_id="N1", source_file="D90_test.md")


def chunks_of(text, sections=(), policy="words80"):
    return chunk_text(text, sections, POLICIES[policy] if isinstance(policy, str) else policy, **IDS)


def numbered(n):
    return " ".join(f"w{i}" for i in range(1, n + 1))


def test_words80_gives_exactly_the_phase2_chunks_for_every_case_study_file():
    for f in load_files():
        assert [c.text for c in chunks_of(f.text)] == words_windows(f.text, 80, 15), f.stem


def test_no_word_is_lost():
    text = numbered(300)
    covered = {w for c in chunks_of(text) for w in c.text.split()}
    assert covered == set(text.split())


def test_no_chunk_is_longer_than_the_limit_and_neighbours_overlap_by_15():
    chunks = chunks_of(numbered(300))
    assert all(len(c.text.split()) <= 80 for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        assert a.text.split()[-15:] == b.text.split()[:15]


def test_a_short_text_is_one_chunk_and_an_empty_text_none():
    assert len(chunks_of("only five words in here")) == 1
    assert chunks_of("   ") == ()


def test_the_window_starts_follow_the_baseline_stepping():
    assert window_starts(200, 80, 15) == [0, 65, 130]
    assert window_starts(80, 80, 15) == [0]


def test_chunks_are_numbered_from_1_with_item_version_and_order_in_the_id():
    chunks = chunks_of(numbered(200))
    assert [c.chunk_id for c in chunks] == ["D90@1#1", "D90@1#2", "D90@1#3"]


def test_the_character_span_points_at_the_chunk_words_in_the_text():
    text = "Title\n\n" + numbered(120)
    for c in chunks_of(text):
        assert text[c.location.char_start:c.location.char_end].split() == c.text.split()


def test_sections80_never_crosses_a_heading():
    text = "# A\n" + numbered(70) + "\n# B\n" + " ".join(f"x{i}" for i in range(60))
    sections = (Section(0, text.index("# B")), Section(text.index("# B"), len(text)))
    chunks = chunks_of(text, sections, "sections80")
    assert len(chunks) == 2
    assert all(not (any(w.startswith("w") for w in c.text.split()) and any(w.startswith("x") for w in c.text.split()))
               for c in chunks)
    assert len(chunks_of(text)) == 2 and "x0" in chunks_of(text)[0].text   # words80 does cross it


def test_sections80_packs_small_sections_together():
    text = "# A\none two\n# B\nthree four\n"
    sections = (Section(0, 12), Section(12, len(text)))
    assert len(chunks_of(text, sections, "sections80")) == 1


def test_a_chunk_records_its_heading_path(tmp_path):
    path = tmp_path / "d.md"
    path.write_text("# Fleet\nintro words\n## Totals\n" + numbered(100), encoding="utf-8")
    doc = MarkdownExtractor().extract(path, DocumentFormat.MARKDOWN)
    chunks = chunks_of(doc.text, doc.sections)
    assert chunks[0].location.heading_path == ("Fleet",)
    assert chunks[-1].location.heading_path == ("Fleet", "Totals")


def test_a_chunk_records_the_pages_it_covers():
    doc = pages_to_document([numbered(50), " ".join(f"p{i}" for i in range(50))], "pdf_text")
    first = chunks_of(doc.text, doc.sections)[0]
    assert (first.location.page_start, first.location.page_end) == (1, 2)
    assert all(re.fullmatch(r"\d+", str(s.page)) for s in doc.sections)


def test_a_policy_with_overlap_as_big_as_the_chunk_is_rejected():
    with pytest.raises(DomainError):
        ChunkingPolicy("bad", 10, 10, False)
