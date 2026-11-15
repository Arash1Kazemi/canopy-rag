"""Find the chunks closest to a question, inside one node only (hard rule H01)."""
import math
from dataclasses import dataclass


def cosine(a, b):
    """The angle between two lists of numbers, as a number from -1 to 1. 1 means they point the same way."""
    dot = sum(x * y for x, y in zip(a, b))
    length = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / length if length else 0.0


@dataclass
class Index:
    chunks: list
    vectors: list


def search(index, query_vector, node_id, k):
    """The k best chunks of one node, best first. A chunk of another node is never returned."""
    scored = [(cosine(query_vector, vector), chunk)
              for chunk, vector in zip(index.chunks, index.vectors) if chunk.node_id == node_id]
    scored.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))  # ties break on the chunk id, so the order is stable
    return [(chunk, score) for score, chunk in scored[:k]]
