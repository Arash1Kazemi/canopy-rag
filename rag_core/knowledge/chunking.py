"""Chunking: cut the extracted text of one version into KnowledgeChunks. The rules are in architecture/chunking_spec.md.

Two named policies:
- words80:    80-word windows with 15 words of overlap over the whole text. This is the Phase 2 baseline, and its chunk
              texts are exactly those of baseline_runner/chunking.py, so earlier results stay comparable.
- sections80: the same windows, but a chunk never crosses a section boundary (a heading or a page), and small
              neighbouring sections are packed together up to 80 words.

Both policies record, for every chunk, the pages, the heading path and the character span it covers.
"""
import re
from dataclasses import dataclass
from typing import Optional

from ..shared.kernel import DomainError
from .model import KnowledgeChunk, SourceLocation

WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class Section:
    """A piece of the extracted text with one heading path and one page. `start` is its offset in the full text."""
    start: int
    end: int
    heading_path: tuple = ()
    page: Optional[int] = None


@dataclass(frozen=True)
class ChunkingPolicy:
    name: str
    words_per_chunk: int
    overlap_words: int
    respect_sections: bool

    def __post_init__(self):
        if self.words_per_chunk <= 0 or not 0 <= self.overlap_words < self.words_per_chunk:
            raise DomainError("a chunk has more than 0 words, and the overlap is at least 0 and smaller than the chunk")


POLICIES = {
    "words80": ChunkingPolicy("words80", 80, 15, respect_sections=False),
    "sections80": ChunkingPolicy("sections80", 80, 15, respect_sections=True),
}
DEFAULT_POLICY = "words80"  # the measured baseline; sections80 waits for an experiment that shows it is better


def window_starts(word_count, size, overlap):
    """Indexes of the first word of each window. Same stepping as the Phase 2 baseline:
    each window starts size - overlap words after the last, and the last window reaches the end."""
    if word_count == 0:
        return []
    starts, start = [0], 0
    while start + size < word_count:
        start += size - overlap
        starts.append(start)
    return starts


def _spans(text, start, end):
    """(start, end) offsets of every word between two offsets of the text."""
    return [(m.start() + start, m.end() + start) for m in WORD.finditer(text[start:end])]


def _groups(sections, text, policy):
    """The stretches of text that windows may not cross. One stretch for words80; packed sections for sections80."""
    if not policy.respect_sections or not sections:
        return [(0, len(text))]
    groups, current, words = [], None, 0
    for s in sections:
        n = len(_spans(text, s.start, s.end))
        if n == 0:
            continue
        if current is not None and words + n <= policy.words_per_chunk:
            current = (current[0], s.end)
            words += n
        else:
            if current is not None:
                groups.append(current)
            current, words = (s.start, s.end), n
    if current is not None:
        groups.append(current)
    return groups


def _section_at(sections, offset):
    for s in sections:
        if s.start <= offset < s.end:
            return s
    return None


def chunk_text(text, sections, policy, *, item_id, version_tag, node_id, source_file):
    """Return the chunks of one version, numbered from 1. `sections` may be empty (no headings, no pages)."""
    chunks = []
    for g_start, g_end in _groups(sections, text, policy):
        spans = _spans(text, g_start, g_end)
        for first in window_starts(len(spans), policy.words_per_chunk, policy.overlap_words):
            window = spans[first:first + policy.words_per_chunk]
            c_start, c_end = window[0][0], window[-1][1]
            covered = [s for s in sections if s.start < c_end and c_start < s.end]
            pages = [s.page for s in covered if s.page is not None]
            head = _section_at(sections, c_start)
            order = len(chunks) + 1
            location = SourceLocation(item_id, version_tag, source_file, c_start, c_end,
                                      page_start=min(pages) if pages else None, page_end=max(pages) if pages else None,
                                      heading_path=head.heading_path if head else ())
            chunks.append(KnowledgeChunk(KnowledgeChunk.make_id(item_id, version_tag, order), node_id, order,
                                         " ".join(text[a:b] for a, b in window), location))
    return tuple(chunks)
