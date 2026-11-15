"""Test doubles: they stand in for the real models, so the code around the models can be tested offline.

FakeEmbedder is a fake: it really embeds, in a simple way (words counted into hashed slots), with no model.
FakeClient is a fake client: embeddings from FakeEmbedder, and chat replies from a plain function.
"""
import hashlib
import math
import re

from .ollama_api import ChatResult, EmbedResult, Stats


class FakeEmbedder:
    def __init__(self, dims=64):
        self.dims = dims

    def vector(self, text):
        slots = [0.0] * self.dims
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.md5(word.encode("utf-8")).digest()  # md5 is stable across runs, unlike hash()
            slots[int.from_bytes(digest[:2], "big") % self.dims] += 1.0
        length = math.sqrt(sum(x * x for x in slots))
        return [x / length for x in slots] if length else slots

    def embed(self, texts):
        return [self.vector(t) for t in texts]


def echo_first_document(prompt, images, json_mode):
    """A fake LLM: it answers with the first document it was given, cited, or refuses if there is none."""
    if json_mode:
        return '{"verdict": "correct", "reason": "fake"}'
    if images:
        return ""
    block = prompt.split("Documents:", 1)[-1].split("Question:", 1)[0]
    match = re.search(r"\[([\w.\-]+)\]\s*(.+)", block)
    if not match:
        return "Insufficient knowledge."
    return f"{match.group(2).strip()[:200]} [{match.group(1)}]"


class FakeClient:
    """Same methods as OllamaClient. It remembers every call, so a test can look at what was sent."""

    def __init__(self, dims=64, reply=echo_first_document):
        self.embedder = FakeEmbedder(dims)
        self.reply = reply
        self.calls = []

    def version(self):
        return "fake"

    def models(self):
        return {}

    def embed(self, model, texts, *, keep_alive="5m"):
        self.calls.append(("embed", model, list(texts)))
        return EmbedResult(self.embedder.embed(texts), Stats(prompt_tokens=sum(len(t.split()) for t in texts)))

    def chat(self, model, messages, *, images=None, options=None, think=None, json_mode=False, keep_alive="5m"):
        self.calls.append(("chat", model, messages[-1]["content"]))
        text = self.reply(messages[-1]["content"], images, json_mode)
        return ChatResult(text, Stats(generated_tokens=len(text.split()), generated_s=1.0))
