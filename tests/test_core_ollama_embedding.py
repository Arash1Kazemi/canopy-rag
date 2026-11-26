"""Test area: the Ollama embedding adapter (Phase 8A, H06). A fake HTTP layer stands in for the server; no network.

Pinned: the Phase 2 formats are reused (P10 plain documents, P09 Instruct/Query questions), the model tag is
qwen3-embedding:0.6b, the address is 127.0.0.1:11500, and an address on another machine is refused.
"""
import pytest

from baseline_runner.ollama_api import OllamaClient, OllamaError
from rag_core.infrastructure.ollama_embedding import DEFAULT_EMBEDDING_TAG, OllamaEmbeddingModel, ollama_url


class FakeHttp:
    """Records each request and answers /api/embed with one small vector per input."""

    def __init__(self, count=None):
        self.calls = []
        self.count = count

    def __call__(self, method, path, payload):
        self.calls.append((method, path, payload))
        n = len(payload["input"]) if self.count is None else self.count
        return {"embeddings": [[float(i), 1.0] for i in range(n)]}


def model(http):
    return OllamaEmbeddingModel(client=OllamaClient(transport=http))


def test_documents_are_sent_as_they_are_in_one_request():
    http = FakeHttp()
    vectors = model(http).embed(["The fleet has 135 buses.", "Route 7"])
    assert vectors == [[0.0, 1.0], [1.0, 1.0]]
    (method, path, payload), = http.calls
    assert (method, path, payload["model"]) == ("POST", "/api/embed", "qwen3-embedding:0.6b")
    assert payload["input"] == ["The fleet has 135 buses.", "Route 7"]
    assert payload["truncate"] is False                     # a too-long chunk is an error, never cut silently


def test_a_question_gets_the_phase_2_qwen3_instruction():
    http = FakeHttp()
    model(http).embed_query("How many buses?")
    assert http.calls[0][2]["input"] == [
        "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:How many buses?"]


def test_the_model_tag_is_the_baseline_embedding_model():
    assert model(FakeHttp()).model_tag == DEFAULT_EMBEDDING_TAG == "qwen3-embedding:0.6b"


def test_no_texts_means_no_request():
    http = FakeHttp()
    assert model(http).embed([]) == [] and http.calls == []


def test_a_short_reply_is_an_error():
    with pytest.raises(OllamaError):
        model(FakeHttp(count=1)).embed(["a", "b"])


def test_the_default_address_is_the_local_server_on_port_11500(monkeypatch):
    monkeypatch.delenv("RAG_OLLAMA_URL", raising=False)
    assert ollama_url({}) == "http://127.0.0.1:11500"
    assert OllamaEmbeddingModel().client.base_url == "http://127.0.0.1:11500"


def test_the_port_may_change_but_only_on_this_machine():
    assert ollama_url({"RAG_OLLAMA_URL": "http://127.0.0.1:11600"}) == "http://127.0.0.1:11600"
    assert ollama_url({"RAG_OLLAMA_URL": "http://localhost:11500"}) == "http://localhost:11500"
    for remote in ("http://10.0.0.5:11500", "http://example.org:11500", "http://127.0.0.1.example.org"):
        with pytest.raises(ValueError, match="H06"):
            ollama_url({"RAG_OLLAMA_URL": remote})


def test_the_environment_variable_is_read(monkeypatch):
    monkeypatch.setenv("RAG_OLLAMA_URL", "http://127.0.0.1:11999")
    assert OllamaEmbeddingModel().client.base_url == "http://127.0.0.1:11999"
    monkeypatch.setenv("RAG_OLLAMA_URL", "http://192.168.1.2:11500")
    with pytest.raises(ValueError):
        OllamaEmbeddingModel()
