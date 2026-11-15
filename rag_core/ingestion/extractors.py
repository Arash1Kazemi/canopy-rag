"""Text extraction adapters, one per DocumentFormat (proposal section 7.3).

| Format   | Adapter               | Needs                                              |
| md, txt  | MarkdownExtractor     | nothing                                            |
| docx     | DocxExtractor         | nothing: a DOCX file is a ZIP of XML files         |
| pdf      | PdfTextExtractor      | pip install pypdf                                  |
| pdf scan | ScannedPdfExtractor   | pip install pypdfium2, and Ollama with an LVM      |
| doc      | DocExtractor          | LibreOffice (converts .doc to .docx, then DocxExtractor) |

Each adapter returns an ExtractedDocument: the text, its sections (headings or pages), and how it was read.
An adapter whose tool is missing says so in available(), and the error names what to install.
"""
import importlib.util
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..knowledge.chunking import Section
from ..knowledge.model import DocumentFormat
from ..shared.kernel import DomainError
from .png import encode_png

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MIN_WORDS_PER_PAGE = 5   # a PDF with fewer words per page than this has no real text layer: it is a scan


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    sections: tuple
    method: str                    # one of knowledge.metadata.EXTRACTION_METHODS
    page_count: Optional[int] = None
    warnings: tuple = field(default=())


class ExtractionError(DomainError):
    pass


def sections_from_headings(lines_with_levels):
    """Build text and Sections from (level or None, line) pairs. The text is the lines joined by newlines.
    A heading starts a new section; its path is the stack of headings above it. Text before the first heading
    gets an empty path."""
    lines = [line for _, line in lines_with_levels]
    text = "\n".join(lines)
    sections, stack, offset = [], [], 0
    current_start, current_path = 0, ()
    for level, line in lines_with_levels:
        if level is not None:
            if offset > current_start:
                sections.append(Section(current_start, offset, current_path))
            stack = [h for h in stack if h[0] < level] + [(level, line.lstrip("#").strip())]
            current_start, current_path = offset, tuple(h[1] for h in stack)
        offset += len(line) + 1
    if len(text) > current_start:
        sections.append(Section(current_start, len(text), current_path))
    return text, tuple(sections)


class MarkdownExtractor:
    formats = (DocumentFormat.MARKDOWN, DocumentFormat.PLAIN_TEXT)

    def available(self):
        return True, ""

    def extract(self, path, fmt):
        raw = Path(path).read_text(encoding="utf-8")
        if fmt == DocumentFormat.PLAIN_TEXT:
            return ExtractedDocument(raw, (Section(0, len(raw)),) if raw else (), "plain_text")
        pairs = []
        for line in raw.split("\n"):
            m = HEADING.match(line)
            pairs.append((len(m.group(1)) if m else None, line))
        text, sections = sections_from_headings(pairs)   # text == raw, so offsets point into the real file text
        return ExtractedDocument(text, sections, "markdown")


class DocxExtractor:
    """Reads word/document.xml with the standard library: paragraphs, heading styles and tables, in order."""
    formats = (DocumentFormat.DOCX,)

    def available(self):
        return True, ""

    @staticmethod
    def _heading_levels(z):
        """styleId -> heading level, read from styles.xml (the style names are 'heading 1', 'Title', ...)."""
        levels = {}
        if "word/styles.xml" not in z.namelist():
            return levels
        for style in ET.fromstring(z.read("word/styles.xml")).iter(f"{W}style"):
            sid = style.get(f"{W}styleId")
            name_el = style.find(f"{W}name")
            name = (name_el.get(f"{W}val") if name_el is not None else sid or "").lower()
            m = re.fullmatch(r"heading ?(\d)", name)
            if m:
                levels[sid] = int(m.group(1))
            elif name == "title":
                levels[sid] = 1
        return levels

    @staticmethod
    def _paragraph_text(p):
        out = []
        for el in p.iter():
            if el.tag == f"{W}t":
                out.append(el.text or "")
            elif el.tag == f"{W}tab":
                out.append("\t")
            elif el.tag in (f"{W}br", f"{W}cr"):
                out.append("\n")
        return "".join(out)

    def extract(self, path, fmt=DocumentFormat.DOCX):
        try:
            with zipfile.ZipFile(path) as z:
                body = ET.fromstring(z.read("word/document.xml")).find(f"{W}body")
                levels = self._heading_levels(z)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as error:
            raise ExtractionError(f"{Path(path).name} is not a readable DOCX file: {error}") from None
        pairs, tables = [], 0
        for block in body if body is not None else []:
            if block.tag == f"{W}p":
                style = block.find(f"{W}pPr/{W}pStyle")
                level = levels.get(style.get(f"{W}val")) if style is not None else None
                text = self._paragraph_text(block).strip()
                if text:
                    pairs.append((level, ("#" * level + " " + text) if level else text))
            elif block.tag == f"{W}tbl":
                tables += 1
                for row in block.iter(f"{W}tr"):
                    cells = [" ".join(self._paragraph_text(p).strip() for p in tc.iter(f"{W}p")).strip() for tc in row.iter(f"{W}tc")]
                    if any(cells):
                        pairs.append((None, "| " + " | ".join(cells) + " |"))
        if not pairs:
            raise ExtractionError(f"{Path(path).name} has no text")
        text, sections = sections_from_headings(pairs)
        return ExtractedDocument(text, sections, "docx_xml", warnings=(f"{tables} table(s) read as rows",) if tables else ())


def _pdf_text_pages(path):
    from pypdf import PdfReader   # imported here: pypdf is optional
    return [(page.extract_text() or "") for page in PdfReader(str(path)).pages]


def pages_to_document(page_texts, method, warnings=()):
    """Join pages into one text with one Section per page, so every chunk knows its pages."""
    text, sections, offset = "", [], 0
    for number, page in enumerate(page_texts, start=1):
        body = page.strip() + "\n\n"
        sections.append(Section(offset, offset + len(body), (), number))
        text += body
        offset += len(body)
    return ExtractedDocument(text, tuple(sections), method, page_count=len(page_texts), warnings=tuple(warnings))


def looks_scanned(page_texts):
    words = sum(len(p.split()) for p in page_texts)
    return words < MIN_WORDS_PER_PAGE * max(1, len(page_texts))


class PdfTextExtractor:
    formats = (DocumentFormat.PDF,)

    def __init__(self, read_pages=None):
        self._read_pages = read_pages or _pdf_text_pages

    def available(self):
        if importlib.util.find_spec("pypdf") is None and self._read_pages is _pdf_text_pages:
            return False, "install pypdf: pip install pypdf"
        return True, ""

    def page_texts(self, path):
        ok, why = self.available()
        if not ok:
            raise ExtractionError(f"cannot read {Path(path).name}: {why}")
        return self._read_pages(path)

    def extract(self, path, fmt=DocumentFormat.PDF):
        pages = self.page_texts(path)
        if looks_scanned(pages):
            raise ExtractionError(f"{Path(path).name} has no text layer (a scan); it needs the LVM")
        return pages_to_document(pages, "pdf_text")


def _render_pages_pdfium(path, scale=2.0):
    """PNG bytes of every page. pypdfium2 renders the page to RGB pixels; png.py writes the PNG (no Pillow needed)."""
    import pypdfium2 as pdfium   # optional
    pngs = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for i in range(len(pdf)):
            bitmap = pdf[i].render(scale=scale, rev_byteorder=True)   # rev_byteorder: RGB instead of BGR
            pngs.append(encode_png(bitmap.width, bitmap.height, bitmap.buffer, bitmap.n_channels, bitmap.stride))
    finally:
        pdf.close()
    return pngs


class ScannedPdfExtractor:
    """A PDF that is only images: render each page and let the LVM read it."""
    formats = (DocumentFormat.PDF,)

    def __init__(self, vision=None, render_pages=None):
        self.vision = vision
        self._render = render_pages or _render_pages_pdfium

    def available(self):
        if self.vision is None:
            return False, "no LVM given: start Ollama and pass --ocr"
        if self._render is _render_pages_pdfium and importlib.util.find_spec("pypdfium2") is None:
            return False, "install the page renderer: pip install pypdfium2"
        return True, ""

    def extract(self, path, fmt=DocumentFormat.PDF):
        ok, why = self.available()
        if not ok:
            raise ExtractionError(f"cannot read the scanned {Path(path).name}: {why}")
        texts = [self.vision.read_page(png) for png in self._render(path)]
        return pages_to_document(texts, "lvm_ocr", warnings=("text read by the LVM: check it against the page",))


def find_soffice():
    found = shutil.which("soffice") or shutil.which("soffice.exe")
    if found:
        return found
    for candidate in (r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if Path(candidate).exists():
            return candidate
    return None


class DocExtractor:
    """Old binary .doc files: LibreOffice converts them to .docx in a temporary folder, then DocxExtractor reads that."""
    formats = (DocumentFormat.DOC,)

    def __init__(self, soffice=None, run=None):
        self.soffice = soffice if soffice is not None else find_soffice()
        self._run = run or subprocess.run

    def available(self):
        if not self.soffice:
            return False, "install LibreOffice (it converts .doc to .docx offline)"
        return True, ""

    def extract(self, path, fmt=DocumentFormat.DOC):
        ok, why = self.available()
        if not ok:
            raise ExtractionError(f"cannot read {Path(path).name}: {why}")
        with tempfile.TemporaryDirectory() as out:
            self._run([self.soffice, "--headless", "--convert-to", "docx", "--outdir", out, str(path)],
                      check=True, capture_output=True, timeout=120)
            converted = Path(out) / (Path(path).stem + ".docx")
            if not converted.exists():
                raise ExtractionError(f"LibreOffice did not convert {Path(path).name}")
            doc = DocxExtractor().extract(converted)
        return ExtractedDocument(doc.text, doc.sections, "doc_convert", warnings=doc.warnings)


class Extractors:
    """Picks the adapter for a format. For a PDF it tries the text layer first and falls back to the LVM."""

    def __init__(self, vision=None, pdf_reader=None, page_renderer=None, doc_extractor=None):
        self.markdown = MarkdownExtractor()
        self.docx = DocxExtractor()
        self.pdf = PdfTextExtractor(pdf_reader)
        self.scan = ScannedPdfExtractor(vision, page_renderer)
        self.doc = doc_extractor or DocExtractor()

    def status(self):
        rows = []
        for label, adapter in (("md, txt", self.markdown), ("docx", self.docx), ("pdf (text)", self.pdf),
                               ("pdf (scan)", self.scan), ("doc", self.doc)):
            ok, why = adapter.available()
            rows.append((label, type(adapter).__name__, "ready" if ok else why))
        return rows

    def extract(self, path, fmt):
        if fmt in self.markdown.formats:
            return self.markdown.extract(path, fmt)
        if fmt == DocumentFormat.DOCX:
            return self.docx.extract(path)
        if fmt == DocumentFormat.DOC:
            return self.doc.extract(path)
        if fmt == DocumentFormat.PDF:
            pages = self.pdf.page_texts(path)
            if not looks_scanned(pages):
                return pages_to_document(pages, "pdf_text")
            return self.scan.extract(path)
        raise ExtractionError(f"no adapter for {fmt}")
