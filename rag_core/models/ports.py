"""Ports: the shapes of the local models, as the core sees them.

The domain and the use cases receive a model as an argument and never import an HTTP client (unit-testing rule 1).
infrastructure/ollama_models.py adapts Ollama to these shapes; tests pass a test double instead.
"""
from typing import Protocol, Sequence


class EmbeddingModel(Protocol):
    def embed(self, texts: Sequence[str]) -> list: ...


class LanguageModel(Protocol):
    def generate(self, prompt: str) -> str: ...


class VisionModel(Protocol):
    def read_page(self, png: bytes) -> str:
        """Return the text of one page image."""
