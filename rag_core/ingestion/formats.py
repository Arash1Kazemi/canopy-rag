"""Detect the DocumentFormat of a file from its first bytes, and check that the extension agrees.

Trusting the extension alone is the common mistake: a renamed file then goes to the wrong reader.
"""
import zipfile
from pathlib import Path

from ..knowledge.model import DocumentFormat
from ..shared.kernel import DomainError

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"   # old binary Office files, such as .doc
EXTENSIONS = {".md": DocumentFormat.MARKDOWN, ".markdown": DocumentFormat.MARKDOWN, ".txt": DocumentFormat.PLAIN_TEXT,
              ".docx": DocumentFormat.DOCX, ".doc": DocumentFormat.DOC, ".pdf": DocumentFormat.PDF}


def sniff(path):
    """The format the bytes say, or None for text (then the extension decides between md and txt)."""
    path = Path(path)
    head = path.read_bytes()[:8]
    if head.startswith(PDF_MAGIC):
        return DocumentFormat.PDF
    if head.startswith(OLE_MAGIC):
        return DocumentFormat.DOC
    if head.startswith(ZIP_MAGIC):
        try:
            with zipfile.ZipFile(path) as z:
                if "word/document.xml" in z.namelist():
                    return DocumentFormat.DOCX
        except zipfile.BadZipFile:
            pass
        raise DomainError(f"{path.name} is a ZIP file but not a Word document")
    return None


def detect(path):
    path = Path(path)
    by_name = EXTENSIONS.get(path.suffix.lower())
    if by_name is None:
        raise DomainError(f"{path.name}: the format {path.suffix or '(none)'} is not supported; "
                          f"supported: {', '.join(sorted(EXTENSIONS))}")
    by_bytes = sniff(path)
    if by_bytes is None:
        if by_name not in (DocumentFormat.MARKDOWN, DocumentFormat.PLAIN_TEXT):
            raise DomainError(f"{path.name} is named {path.suffix} but its bytes look like plain text")
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise DomainError(f"{path.name} is not UTF-8 text") from None
        return by_name
    if by_bytes != by_name:
        raise DomainError(f"{path.name} is named {path.suffix} but its bytes say it is {by_bytes.value}")
    return by_bytes
