"""Split files into chunks. The baseline uses the simplest usual way: windows of words with some overlap."""
from dataclasses import dataclass

from .config import CHUNK_CONFIGS


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


def make_chunks(files, config_name):
    setting = CHUNK_CONFIGS[config_name]
    chunks = []
    for f in files:
        pieces = [f.text.strip()] if setting is None else words_windows(f.text, *setting)
        for n, piece in enumerate(pieces, start=1):
            chunks.append(Chunk(f"{f.stem}#{n}", f.stem, f.doc_id, f.node_id, piece))
    return chunks
