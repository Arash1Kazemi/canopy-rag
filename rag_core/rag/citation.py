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
