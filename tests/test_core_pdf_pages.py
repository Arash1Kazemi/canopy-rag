"""Test area: Ingestion (PDF pages). A PDF is read page by page: a page with a text layer is read as text, a page
without one is rendered and read by the vision model (LVM). Page numbers survive into chunks and citations.
The tests that need pypdf or pypdfium2 are skipped when the package is missing; none needs a running model."""
import importlib.util

import pytest

from core_builders import small_hierarchy
from rag_core.fakes import FixedClock, StubVisionModel, stub_page_renderer, stub_pdf_reader
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository
from rag_core.ingestion.extractors import ExtractionError, Extractors
from rag_core.ingestion.image_pdf import PageImage, encode_image_pdf
from rag_core.ingestion.png import SIGNATURE
from rag_core.ingestion.samples import text_to_pdf
from rag_core.ingestion.service import NEW_ITEM, IngestionService, RegistrationRequest
from rag_core.knowledge.model import DocumentFormat
from rag_core.rag.citation import Citation

HAS_PYPDF = importlib.util.find_spec("pypdf") is not None
HAS_PDFIUM = importlib.util.find_spec("pypdfium2") is not None
TEXT_PAGE = "The pilot cut peak load on Route 7 from 94 percent to 71 percent."
SCANNED_PAGE = "Decision: the Route 7 pilot starts on 4 August 2025 for 8 weeks."
LONG_TEXT, LONG_SCAN = " ".join([TEXT_PAGE] * 4), " ".join([SCANNED_PAGE] * 4)   # 52 words each: too big to pack


def grey_page(width=40, height=20, shade=200):
    return PageImage(width, height, bytes([shade]) * (width * height), channels=1, width_pt=200, height_pt=100)


# --- the image-only PDF writer
def test_an_image_only_pdf_has_no_font_and_no_text_objects():
    data = encode_image_pdf([grey_page(), grey_page(shade=90)])
    assert data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")
    assert b"/Font" not in data and b"BT" not in data      # BT ... ET is how a PDF draws text
    assert data.count(b"/Subtype /Image") == 2


def test_the_same_pixels_always_give_the_same_bytes():
    assert encode_image_pdf([grey_page()]) == encode_image_pdf([grey_page()])


def test_the_image_pdf_writer_refuses_bad_input():
    with pytest.raises(ValueError):
        encode_image_pdf([])
    with pytest.raises(ValueError, match="smaller"):
        encode_image_pdf([PageImage(10, 10, b"\x00" * 5)])
    with pytest.raises(ValueError, match="channels"):
        encode_image_pdf([PageImage(1, 1, b"\x00\x00", channels=2)])


@pytest.mark.skipif(not HAS_PYPDF, reason="pypdf is not installed")
def test_pypdf_finds_the_pages_of_an_image_only_pdf_but_no_text(tmp_path):
    from pypdf import PdfReader
    path = tmp_path / "scan.pdf"
    path.write_bytes(encode_image_pdf([grey_page(), grey_page()]))
    reader = PdfReader(str(path))
    assert len(reader.pages) == 2
    assert all(not (page.extract_text() or "").strip() for page in reader.pages)
    assert [float(x) for x in reader.pages[0].mediabox[2:]] == [200.0, 100.0]


# --- page by page, with stubs for pypdf, the renderer and the LVM
def extract(pages, vision=None):
    return Extractors(vision=vision, pdf_reader=stub_pdf_reader(pages),
                      page_renderer=stub_page_renderer(len(pages))).extract("any.pdf", DocumentFormat.PDF)


def test_a_mixed_pdf_reads_page_1_from_text_and_page_2_with_the_lvm():
    lvm = StubVisionModel([SCANNED_PAGE])
    doc = extract([TEXT_PAGE, ""], lvm)
    assert lvm.seen == [b"png-2"]                                # only the page without text was rendered and sent
    assert doc.method == "pdf_mixed" and doc.page_count == 2
    page_of = {s.page: doc.text[s.start:s.end] for s in doc.sections}
    assert TEXT_PAGE in page_of[1] and SCANNED_PAGE in page_of[2]
    assert any("page 2" in w and "LVM" in w for w in doc.warnings)


def test_only_the_pages_without_a_text_layer_go_to_the_lvm():
    lvm = StubVisionModel(["Page two text read from the image.", "Page four text read from the image."])
    doc = extract([TEXT_PAGE, "  ", TEXT_PAGE, "7"], lvm)        # "7" alone is a page number, not a text layer
    assert lvm.seen == [b"png-2", b"png-4"]
    assert [s.page for s in doc.sections] == [1, 2, 3, 4]
    assert "Page four" in doc.text[doc.sections[3].start:doc.sections[3].end]


def test_a_pdf_whose_every_page_has_text_never_calls_the_lvm():
    lvm = StubVisionModel([])
    doc = extract([TEXT_PAGE, TEXT_PAGE], lvm)
    assert doc.method == "pdf_text" and lvm.seen == []


def test_a_pdf_with_no_text_at_all_is_read_by_the_lvm_page_by_page():
    lvm = StubVisionModel(["First scanned page words here.", "Second scanned page words here."])
    doc = extract(["", ""], lvm)
    assert doc.method == "lvm_ocr" and lvm.seen == [b"png-1", b"png-2"]
    assert [s.page for s in doc.sections] == [1, 2]


def test_a_mixed_pdf_without_an_lvm_keeps_the_text_pages_and_names_the_missing_page():
    doc = extract([TEXT_PAGE, TEXT_PAGE, ""])
    assert doc.method == "pdf_text" and TEXT_PAGE in doc.text
    assert any("page 3" in w and "--ocr" in w for w in doc.warnings)


def test_a_fully_scanned_pdf_without_an_lvm_still_says_what_to_do():
    with pytest.raises(ExtractionError, match="start Ollama"):
        extract(["", ""])


# --- page numbers reach the chunks and the citations
def ingest(path, policy, vision=None, pdf_reader=None, renderer=None):
    service = IngestionService(small_hierarchy(), InMemoryKnowledgeRepository(),
                               Extractors(vision=vision, pdf_reader=pdf_reader, page_renderer=renderer),
                               policy=policy, clock=FixedClock())
    result = service.register(RegistrationRequest(path, "D90", "N1", "1", "Pilot pages", source_file=f"N1/{path.name}"))
    assert result.outcome == NEW_ITEM, result.detail
    return service.repo.get("D90").active_version


def test_sections80_chunks_of_a_mixed_pdf_cite_the_page_they_came_from(tmp_path):
    pdf = text_to_pdf("x", tmp_path / "D90_pilot_pages.pdf")
    version = ingest(pdf, "sections80", StubVisionModel([LONG_SCAN]), stub_pdf_reader([LONG_TEXT, ""]), stub_page_renderer(2))
    assert version.metadata["page_count"] == "2" and version.metadata["extraction_method"] == "pdf_mixed"
    pages = [(c.location.page_start, c.location.page_end) for c in version.chunks]
    assert pages == [(1, 1), (2, 2)]
    citation = Citation.of_chunk(version.chunks[1])
    assert citation.render() == "[D90_pilot_pages]"
    assert citation.render_long() == "[D90_pilot_pages, p. 2, chunk D90@1#2]"


def test_a_words80_chunk_that_crosses_a_page_cites_both_pages(tmp_path):
    pdf = text_to_pdf("x", tmp_path / "D90_pilot_pages.pdf")
    version = ingest(pdf, "words80", StubVisionModel([SCANNED_PAGE]), stub_pdf_reader([TEXT_PAGE, ""]), stub_page_renderer(2))
    assert len(version.chunks) == 1
    assert Citation.of_chunk(version.chunks[0]).render_long() == "[D90_pilot_pages, pp. 1-2, chunk D90@1#1]"


# --- the same with a real PDF file: pypdf reads the text page, pypdfium2 renders the scanned page
def mixed_pdf(tmp_path):
    from pypdf import PdfReader, PdfWriter
    text_pdf = text_to_pdf(LONG_TEXT, tmp_path / "text.pdf")
    scan_pdf = tmp_path / "scan.pdf"
    scan_pdf.write_bytes(encode_image_pdf([grey_page(120, 60)]))
    writer = PdfWriter()
    for source in (text_pdf, scan_pdf):
        for page in PdfReader(str(source)).pages:
            writer.add_page(page)
    out = tmp_path / "D90_pilot_pages.pdf"
    with out.open("wb") as handle:
        writer.write(handle)
    return out


@pytest.mark.skipif(not (HAS_PYPDF and HAS_PDFIUM), reason="pypdf and pypdfium2 are needed")
def test_a_real_two_page_mixed_pdf_is_read_page_by_page(tmp_path):
    lvm = StubVisionModel([SCANNED_PAGE])
    doc = Extractors(vision=lvm).extract(mixed_pdf(tmp_path), DocumentFormat.PDF)
    assert len(lvm.seen) == 1 and lvm.seen[0].startswith(SIGNATURE)   # one real PNG, of page 2 only
    assert doc.method == "pdf_mixed" and [s.page for s in doc.sections] == [1, 2]
    assert "Route 7 from 94 percent" in " ".join(doc.text[doc.sections[0].start:doc.sections[0].end].split())
    assert SCANNED_PAGE in doc.text[doc.sections[1].start:doc.sections[1].end]


@pytest.mark.skipif(not (HAS_PYPDF and HAS_PDFIUM), reason="pypdf and pypdfium2 are needed")
def test_a_real_mixed_pdf_keeps_its_page_numbers_in_the_citations(tmp_path):
    version = ingest(mixed_pdf(tmp_path), "sections80", StubVisionModel([LONG_SCAN]))
    assert [Citation.of_chunk(c).render_long() for c in version.chunks] == [
        "[D90_pilot_pages, p. 1, chunk D90@1#1]", "[D90_pilot_pages, p. 2, chunk D90@1#2]"]
