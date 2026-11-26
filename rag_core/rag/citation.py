"""The citation model. The rules are in architecture/citation_model.md.

An answer cites a file stem in square brackets, as in Phase 2: [D10_bus_fleet_inventory_v2]. The grading rules
(GR4, GR5) work on file stems, so the short form stays. A Citation built from a chunk also knows the chunk, the
version and the pages, so a person can find the exact place; render_long() shows that.
"""
import re
from dataclasses import dataclass
from typing import Optional

from ..shared.kernel import DomainError

BRACKET = re.compile(r"\[([^\[\]]+)\]")
STEM = re.compile(r"[A-Za-z0-9_.\-]+")


@dataclass(frozen=True)
class Citation:
    source_stem: str
    chunk_id: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    heading_path: tuple = ()

    def __post_init__(self):
        if not STEM.fullmatch(self.source_stem or ""):
            raise DomainError(f"a citation names a file stem with letters, digits, '.', '_' or '-', not {self.source_stem!r}")

    @classmethod
    def of_chunk(cls, chunk):
        loc = chunk.location
        return cls(loc.source_stem, chunk.chunk_id, loc.page_start, loc.page_end, loc.heading_path)

    def render(self):
        """The short form an answer uses."""
        return f"[{self.source_stem}]"

    def render_long(self):
        """For people: [D19_meeting_minutes_2025-06-18, p. 1, Decisions, chunk D19@1#2]."""
        parts = [self.source_stem]
        if self.page_start is not None:
            parts.append(f"p. {self.page_start}" if self.page_start == self.page_end else f"pp. {self.page_start}-{self.page_end}")
        if self.heading_path:
            parts.append(" > ".join(self.heading_path))
        if self.chunk_id:
            parts.append(f"chunk {self.chunk_id}")
        return "[" + ", ".join(parts) + "]"


def parse_citations(answer):
    """The file stems an answer cites, in order, each once. '[D10_x, D13_y]' counts as two citations."""
    found = []
    for bracket in BRACKET.findall(answer):
        for part in bracket.split(","):
            stem = part.strip()
            if STEM.fullmatch(stem) and stem not in found:
                found.append(stem)
    return found


KNOWN_EXTENSIONS = (".md", ".txt", ".pdf", ".docx", ".doc")


@dataclass(frozen=True)
class CitationCheck:
    """The result of checking the citations of one answer against the stems that were given to the model (H09).

    valid_stems: cited stems that were given, in order of first appearance, written as given (not as the model wrote them).
    invalid_stems: cited stems that were not given, as the model wrote them.
    cleaned_text: the answer with every invalid stem removed; a bracket left empty is removed with the space before it.
    """
    valid_stems: tuple
    invalid_stems: tuple
    cleaned_text: str


def _canonical(stem, allowed):
    """The allowed stem this cited stem means, or None. A file extension after the stem ([D10_x.md]) is tolerated,
    as in the Phase 2 grading; case and spelling must match exactly."""
    if stem in allowed:
        return stem
    for ext in KNOWN_EXTENSIONS:
        if stem.lower().endswith(ext) and stem[: -len(ext)] in allowed:
            return stem[: -len(ext)]
    return None


def check_citations(answer, allowed_stems):
    """Split the citations of an answer into valid (given to the model) and invalid (anything else), and remove the
    invalid ones from the text. Text in brackets that is not a stem, such as [the report above], is left alone."""
    allowed = set(allowed_stems)
    valid, invalid = [], []
    removed = []

    def rewrite(match):
        parts = [p.strip() for p in match.group(1).split(",")]
        kept = []
        for part in parts:
            if not STEM.fullmatch(part):
                kept.append(part)          # not a citation: leave it as it was written
                continue
            canon = _canonical(part, allowed)
            if canon is None:
                removed.append(part)
                if part not in invalid:
                    invalid.append(part)
                continue
            if canon not in valid:
                valid.append(canon)
            kept.append(canon)
        return f"[{', '.join(kept)}]" if kept else ""

    cleaned = BRACKET.sub(rewrite, answer)
    if removed:                                                       # tidy the gap a removed bracket leaves
        cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return CitationCheck(tuple(valid), tuple(invalid), cleaned)
