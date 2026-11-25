"""Phase 4: make the real DOCX and PDF files of the case study from their Markdown sources. Run from UNI-Project/:

    ../.venv/bin/python.exe -I scripts/make_real_files.py            make every real file the manifest names, then check them
    ../.venv/bin/python.exe -I scripts/make_real_files.py --check    only check the files that are there

The manifest (case_study/documents_manifest.csv) decides what is made: each row with a `real_file` gets one, in the
same node folder and with the same stem as its Markdown file, so citations and the answer key stay the same.
`real_format` says how:

  docx            LibreOffice opens the Markdown and saves it as Word (DOCX)
  pdf_text        LibreOffice opens the Markdown and exports a PDF with a text layer
  pdf_image_only  as pdf_text, then every page is rendered to grey pixels (pypdfium2) and written back as a PDF that
                  holds only the pictures (rag_core/ingestion/image_pdf.py): no text layer, like a scan. Pillow is not needed.

Needs LibreOffice (with Markdown import, version 25.8 or newer) and pypdfium2; the check needs pypdf. Nothing is
downloaded. The Markdown files are only read. LibreOffice writes the date into a PDF, so a new run changes the bytes of
the text PDFs but not their text; the image-only PDF comes out the same each time.
"""
import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from rag_core.ingestion.case_study import REAL_FORMATS                       # noqa: E402
from rag_core.ingestion.extractors import DocxExtractor, find_soffice        # noqa: E402
from rag_core.ingestion.image_pdf import PageImage, encode_image_pdf          # noqa: E402

CASE = PROJECT / "case_study"
DOCS = CASE / "documents"
SCALE = 2.0   # 72 points per inch x 2 = 144 dots per inch: small enough for a 4 GB laptop, sharp enough for the LVM


def real_rows():
    with (CASE / "documents_manifest.csv").open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("real_file")]


def libreoffice(soffice, source, target_format, out_dir, profile):
    """Convert one file with LibreOffice, headless, with its own throw-away user profile (so an open LibreOffice
    window does not block it). Returns the converted file."""
    command = [soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--convert-to", target_format,
               "--outdir", str(out_dir), str(source)]
    subprocess.run(command, check=True, capture_output=True, timeout=180)
    made = out_dir / (source.stem + "." + target_format.split(":")[0])
    if not made.is_file():
        raise SystemExit(f"LibreOffice did not convert {source.name} to {target_format}")
    return made


def image_only_copy(text_pdf, out_path):
    """Render each page of a text PDF to grey pixels and write a PDF that holds only those pictures."""
    import pypdfium2 as pdfium
    pages = []
    pdf = pdfium.PdfDocument(str(text_pdf))
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            width_pt, height_pt = page.get_size()
            bitmap = page.render(scale=SCALE, grayscale=True)
            pages.append(PageImage(bitmap.width, bitmap.height, bytes(bitmap.buffer), bitmap.n_channels, bitmap.stride,
                                   width_pt, height_pt))
    finally:
        pdf.close()
    out_path.write_bytes(encode_image_pdf(pages))
    return out_path


def make(rows):
    soffice = find_soffice()
    if not soffice:
        raise SystemExit("LibreOffice was not found: install it, or put soffice on the PATH")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        profile = tmp / "profile"
        for row in rows:
            source, target = DOCS / row["file"], DOCS / row["real_file"]
            fmt = row["real_format"]
            if fmt == "docx":
                shutil.copyfile(libreoffice(soffice, source, "docx", tmp, profile), target)
            elif fmt == "pdf_text":
                shutil.copyfile(libreoffice(soffice, source, "pdf", tmp, profile), target)
            elif fmt == "pdf_image_only":
                image_only_copy(libreoffice(soffice, source, "pdf", tmp, profile), target)
            else:
                raise SystemExit(f"{row['doc_id']}: unknown real_format {fmt!r}; known: {', '.join(REAL_FORMATS)}")
            print(f"made  {row['real_file']}  ({fmt}, {target.stat().st_size:,} bytes)")


def words(text):
    return len(text.split())


def check(rows):
    """Each real file exists and reads as promised. Returns the number of problems."""
    from pypdf import PdfReader
    problems = 0
    for row in rows:
        path, fmt = DOCS / row["real_file"], row["real_format"]
        source_words = words((DOCS / row["file"]).read_text(encoding="utf-8"))
        if not path.is_file():
            print(f"MISSING  {row['real_file']}")
            problems += 1
            continue
        if fmt == "docx":
            doc = DocxExtractor().extract(path)
            ok = words(doc.text) >= source_words // 2 and any(s.heading_path for s in doc.sections)
            detail = f"{words(doc.text)} words, headings {'kept' if ok else 'LOST'}"
        else:
            pages = [(page.extract_text() or "") for page in PdfReader(str(path)).pages]
            found = sum(words(p) for p in pages)
            ok = found == 0 if fmt == "pdf_image_only" else found >= source_words // 2
            detail = f"{len(pages)} page(s), {found} words in the text layer"
        print(f"{'ok' if ok else 'WRONG':<8} {row['real_file']}  ({fmt}: {detail}; the Markdown has {source_words} words)")
        problems += 0 if ok else 1
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only check the real files that are there")
    args = parser.parse_args(argv)
    rows = real_rows()
    if not args.check:
        make(rows)
    problems = check(rows)
    print(f"{len(rows)} real file(s), {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
