"""Ports: the shapes of the local models, as the core sees them.

The domain and the use cases receive a model as an argument and never import an HTTP client (unit-testing rule 1).
infrastructure/ollama_models.py adapts Ollama to these shapes; tests pass a test double instead.
"""
from typing import Protocol, Sequence


class EmbeddingModel(Protocol):
    """Phase 8: documents and questions are embedded differently. qwen3-embedding wants an instruction before a question
    and none before a document (prompts P09 and P10), so the adapter, not the core, formats the text."""
    model_tag: str   # stored with every vector; a different tag means the index is rebuilt

    def embed(self, texts: Sequence[str]) -> list:
        """One vector per document text (a chunk), in order."""

    def embed_query(self, text: str) -> list:
        """One vector for a question."""


class LanguageModel(Protocol):
    def generate(self, prompt: str) -> str: ...


class VisionModel(Protocol):
    def read_page(self, png: bytes) -> str:
        """Return the text of one page image."""
