"""Test doubles for the core, in one place (unit-testing rule 3). tests/test_core_fakes.py tests them."""
from pathlib import Path


class FixedClock:
    """A stub clock: always the same time, so metadata is the same on every run."""

    def __init__(self, value="2026-11-01T10:00:00Z"):
        self.value = value

    def __call__(self):
        return self.value


class StubVisionModel:
    """A stub LVM that is also a spy: it returns fixed page texts in order and remembers what it was given."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.seen = []

    def read_page(self, png):
        self.seen.append(png)
        return self.pages[len(self.seen) - 1]


def stub_pdf_reader(pages):
    """A stub for pypdf: returns these page texts for any file."""
    return lambda path: list(pages)


def stub_page_renderer(count):
    """A stub page renderer: `count` fake PNG images."""
    return lambda path: [f"png-{i}".encode() for i in range(1, count + 1)]


class SpyRunner:
    """Stands in for subprocess.run when LibreOffice converts a .doc. It records the command and writes the
    .docx that LibreOffice would have written, made from `docx_bytes`."""

    def __init__(self, docx_bytes):
        self.docx_bytes = docx_bytes
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        out = Path(command[command.index("--outdir") + 1])
        (out / (Path(command[-1]).stem + ".docx")).write_bytes(self.docx_bytes)
