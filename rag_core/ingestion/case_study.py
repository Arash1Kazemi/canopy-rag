"""Turn the case-study manifest into registration requests. The case study stays read-only.

The Markdown file of each row (`file`) is the source of truth. Some rows also name a real file (`real_file`): a DOCX or
PDF that scripts/make_real_files.py made from the Markdown with LibreOffice, in the same node folder and with the same
stem, so citations and the answer key stay the same. `real_format` says what kind it is (REAL_FORMATS).
"""
import csv
from pathlib import Path

from .service import RegistrationRequest

REAL_FORMATS = {"docx": ".docx", "pdf_text": ".pdf", "pdf_image_only": ".pdf"}   # real_format -> file suffix
NEEDS_LVM = "pdf_image_only"


def manifest_requests(case_dir, documents_dir=None, replace_suffix=None, *, read_rows=None, real_files=False, lvm=False):
    """One request per manifest row, in manifest order. The item id is the doc_id (D10), the version tag is the
    manifest version.

    With `real_files` a row that names a real file is read from it (the ingest-case-study command does this; the
    default reads the Markdown, so Phase 2 and Phase 5 comparisons keep reading what they read before). An image-only PDF needs the LVM, so
    without `lvm` its Markdown is read instead, and the request carries a note that says so. A manifest without the
    real_file column (an older copy in the project database) reads the Markdown files.

    `documents_dir` and `replace_suffix` read converted copies instead, for example the DOCX files in team/C/files/ with
    replace_suffix='.docx'. A copy may sit in the node subfolder or directly in documents_dir. A file with no copy is
    read from the case study as usual. The file stem stays the same, so citations stay the same."""
    case_dir = Path(case_dir)
    originals = case_dir / "documents"
    copies = Path(documents_dir) if documents_dir else None
    manifest = case_dir / "documents_manifest.csv"
    if read_rows is None:
        with manifest.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = read_rows(manifest)
    requests = []
    for row in rows:
        relative = Path(row["file"])
        path, notes = originals / relative, ()
        real = (row.get("real_file") or "").strip()
        if copies is not None:
            suffix = replace_suffix or relative.suffix
            candidates = [copies / relative.with_suffix(suffix), copies / relative.with_suffix(suffix).name]
            path = next((c for c in candidates if c.exists()), path)
        elif real_files and real:
            if row.get("real_format") == NEEDS_LVM and not lvm:
                notes = (f"read the Markdown {relative.name}: the image-only {Path(real).name} needs the LVM "
                         f"(start Ollama and pass --ocr to read it)",)
            else:
                relative = Path(real)
                path = originals / relative
        requests.append(RegistrationRequest(path=path, item_id=row["doc_id"], node_id=row["node_id"],
                                            version_tag=row["version"], title=row["title"], language=row["language"],
                                            source_file=relative.with_suffix(path.suffix).as_posix(), notes=notes))
    return requests
