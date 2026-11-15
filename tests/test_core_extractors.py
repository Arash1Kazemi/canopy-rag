"""Test area: Ingestion (format detection and text extraction). Real PDF parsing runs only when pypdf is installed."""
import importlib.util

import pytest

from rag_core.fakes import SpyRunner, StubVisionModel, stub_page_renderer, stub_pdf_reader
from rag_core.ingestion.extractors import DocExtractor, DocxExtractor, ExtractionError, Extractors, MarkdownExtractor, PdfTextExtractor
from rag_core.ingestion.formats import detect
from rag_core.ingestion.samples import markdown_to_docx, text_to_pdf
from rag_core.knowledge.model import DocumentFormat
from rag_core.shared.kernel import DomainError

MD = "# Fleet\nIntro line.\n## Totals\n| Type | Buses |\n|---|---:|\n| Diesel | 78 |\n| **Total** | **135** |\nEnd.\n"


# --- formats
def test_formats_are_detected_from_the_bytes(tmp_path):
    (tmp_path / "a.md").write_text(MD, encoding="utf-8")
    markdown_to_docx(MD, tmp_path / "a.docx")
    text_to_pdf("hello", tmp_path / "a.pdf")
    assert [detect(tmp_path / n) for n in ("a.md", "a.docx", "a.pdf")] == [DocumentFormat.MARKDOWN, DocumentFormat.DOCX, DocumentFormat.PDF]


def test_a_renamed_file_is_caught(tmp_path):
    text_to_pdf("hello", tmp_path / "report.docx")
    with pytest.raises(DomainError, match="bytes say it is pdf"):
        detect(tmp_path / "report.docx")


def test_a_text_file_named_pdf_is_caught(tmp_path):
    (tmp_path / "fake.pdf").write_text("just text", encoding="utf-8")
    with pytest.raises(DomainError, match="look like plain text"):
        detect(tmp_path / "fake.pdf")


def test_an_unsupported_extension_is_named(tmp_path):
    (tmp_path / "slides.pptx").write_bytes(b"PK\x03\x04")
    with pytest.raises(DomainError, match="not supported"):
        detect(tmp_path / "slides.pptx")


def test_an_old_doc_file_is_recognised_by_its_signature(tmp_path):
    (tmp_path / "old.doc").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 100)
    assert detect(tmp_path / "old.doc") == DocumentFormat.DOC


# --- markdown and docx
def test_markdown_text_is_the_file_text_and_headings_make_sections(tmp_path):
    (tmp_path / "a.md").write_text(MD, encoding="utf-8")
    doc = MarkdownExtractor().extract(tmp_path / "a.md", DocumentFormat.MARKDOWN)
    assert doc.text == MD
    assert [s.heading_path for s in doc.sections] == [("Fleet",), ("Fleet", "Totals")]
    assert doc.sections[-1].end == len(MD)


def test_docx_keeps_headings_paragraphs_and_table_rows_in_order(tmp_path):
    doc = DocxExtractor().extract(markdown_to_docx(MD, tmp_path / "a.docx"))
    assert doc.text.split("\n") == ["# Fleet", "Intro line.", "## Totals", "| Type | Buses |", "| Diesel | 78 |",
                                    "| **Total** | **135** |", "End."]
    assert [s.heading_path for s in doc.sections] == [("Fleet",), ("Fleet", "Totals")]
    assert doc.method == "docx_xml" and doc.warnings == ("1 table(s) read as rows",)


def test_a_broken_docx_gives_a_clear_error(tmp_path):
    (tmp_path / "broken.docx").write_bytes(b"PK\x03\x04 not really a zip")
    with pytest.raises(ExtractionError, match="not a readable DOCX"):
        DocxExtractor().extract(tmp_path / "broken.docx")


# --- pdf, with a stub in place of pypdf
def test_a_pdf_with_a_text_layer_gives_one_section_per_page(tmp_path):
    pdf = text_to_pdf("x", tmp_path / "a.pdf")
    doc = Extractors(pdf_reader=stub_pdf_reader(["Page one has enough words here.", "Page two also has words."])).extract(pdf, DocumentFormat.PDF)
    assert doc.method == "pdf_text" and doc.page_count == 2
    assert [s.page for s in doc.sections] == [1, 2]


def test_a_scanned_pdf_falls_back_to_the_lvm(tmp_path):
    pdf = text_to_pdf("x", tmp_path / "scan.pdf")
    lvm = StubVisionModel(["Meeting minutes 18 June 2025. Decision: run the Route 7 pilot."])
    doc = Extractors(vision=lvm, pdf_reader=stub_pdf_reader([""]), page_renderer=stub_page_renderer(1)).extract(pdf, DocumentFormat.PDF)
    assert doc.method == "lvm_ocr" and "Route 7 pilot" in doc.text
    assert lvm.seen == [b"png-1"]


def test_a_scanned_pdf_without_an_lvm_says_what_to_do(tmp_path):
    pdf = text_to_pdf("x", tmp_path / "scan.pdf")
    with pytest.raises(ExtractionError, match="start Ollama"):
        Extractors(pdf_reader=stub_pdf_reader(["   "])).extract(pdf, DocumentFormat.PDF)


def test_the_pdf_reader_alone_refuses_a_scan(tmp_path):
    with pytest.raises(ExtractionError, match="no text layer"):
        PdfTextExtractor(stub_pdf_reader(["", ""])).extract(text_to_pdf("x", tmp_path / "s.pdf"))


@pytest.mark.skipif(importlib.util.find_spec("pypdf") is None, reason="pypdf is not installed")
def test_a_real_pdf_text_layer_is_read_by_pypdf(tmp_path):
    pdf = text_to_pdf("The fleet has 135 buses in July 2025.\n" * 3, tmp_path / "real.pdf")
    doc = PdfTextExtractor().extract(pdf)
    assert "135 buses" in doc.text


# --- doc, with a spy in place of LibreOffice
def test_a_doc_file_is_converted_by_libreoffice_then_read(tmp_path):
    docx = markdown_to_docx(MD, tmp_path / "made.docx").read_bytes()
    (tmp_path / "old.doc").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    runner = SpyRunner(docx)
    doc = DocExtractor(soffice="soffice", run=runner).extract(tmp_path / "old.doc")
    assert doc.method == "doc_convert" and "135" in doc.text
    assert runner.calls[0][:4] == ["soffice", "--headless", "--convert-to", "docx"]


def test_without_libreoffice_a_doc_file_says_what_to_install(tmp_path):
    with pytest.raises(ExtractionError, match="LibreOffice"):
        DocExtractor(soffice="").extract(tmp_path / "old.doc")


def test_png_encoder_writes_a_valid_header():
    import struct, zlib
    from rag_core.ingestion.png import SIGNATURE, encode_png
    pixels = bytes([255, 0, 0, 0, 255, 0, 9, 9]) + bytes([0, 0, 255, 255, 255, 255, 9, 9])   # 2x2 RGB, stride 8
    png = encode_png(2, 2, pixels, channels=3, stride=8)
    assert png.startswith(SIGNATURE)
    width, height, depth, colour = struct.unpack(">IIBB", png[16:26])
    assert (width, height, depth, colour) == (2, 2, 8, 2)
    idat = png.index(b"IDAT")
    length = struct.unpack(">I", png[idat - 4:idat])[0]
    assert zlib.decompress(png[idat + 4:idat + 4 + length]) == b"\x00" + pixels[:6] + b"\x00" + pixels[8:14]
    assert png.endswith(b"IEND\xaeB`\x82")
