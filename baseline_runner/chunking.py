"""Split files into chunks. The baseline uses the simplest usual way: windows of words with some overlap.
The CORE_CHUNKS settings (sections80) are cut by the core's chunking instead, with the Markdown headings as sections,
so E3 measures exactly what ingestion stores."""
from dataclasses import dataclass

from rag_core.ingestion.extractors import HEADING, sections_from_headings
from rag_core.knowledge.chunking import POLICIES, chunk_text
from rag_core.knowledge.model import KnowledgeItemId, VersionTag

from .config import CHUNK_CONFIGS, CORE_CHUNKS


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # D18_complaint_log_Q2_2025#2
    stem: str
    doc_id: str
    node_id: str
    text: str


def words_windows(text, size, overlap):
    """Windows of `size` words. Each window starts `size - overlap` words after the last one,
    so every word is in at least one window and the last window reaches the end of the text."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("size must be positive and overlap must be at least 0 and less than size")
    words = text.split()
    if len(words) <= size:
        return [" ".join(words)] if words else []
    windows, start = [], 0
    while True:
        windows.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            return windows
        start += size - overlap


def core_chunks(f, policy_name):
    """The core's chunks of one Markdown file: a heading starts a section, as in MarkdownExtractor."""
    pairs = []
    for line in f.text.split("\n"):
        m = HEADING.match(line)
        pairs.append((len(m.group(1)) if m else None, line))
    text, sections = sections_from_headings(pairs)
    return chunk_text(text, sections, POLICIES[policy_name], item_id=KnowledgeItemId(f.doc_id),
                      version_tag=VersionTag(f.version), node_id=f.node_id, source_file=f"{f.stem}.md")


def make_chunks(files, config_name):
    if config_name in CORE_CHUNKS:
        return [Chunk(f"{f.stem}#{c.order}", f.stem, f.doc_id, f.node_id, c.text)
                for f in files for c in core_chunks(f, config_name)]
    setting = CHUNK_CONFIGS[config_name]
    chunks = []
    for f in files:
        pieces = [f.text.strip()] if setting is None else words_windows(f.text, *setting)
        for n, piece in enumerate(pieces, start=1):
            chunks.append(Chunk(f"{f.stem}#{n}", f.stem, f.doc_id, f.node_id, piece))
    return chunks
