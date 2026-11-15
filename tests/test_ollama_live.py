"""Integration tests: they need the local Ollama server. They are skipped when it is not running."""
import pytest

from baseline_runner.ollama_api import OllamaClient, OllamaError

pytestmark = pytest.mark.integration


def server_or_skip():
    client = OllamaClient(timeout=30)
    try:
        client.version()
    except OllamaError:
        pytest.skip("the local Ollama server is not running")
    return client


def test_the_server_answers_on_this_machine():
    assert server_or_skip().version()


def test_a_shortlisted_embedding_model_returns_one_vector_per_text():
    client = server_or_skip()
    if "qwen3-embedding:0.6b" not in client.models():
        pytest.skip("qwen3-embedding:0.6b is not downloaded")
    result = client.embed("qwen3-embedding:0.6b", ["a bus", "a boat"])
    assert len(result.vectors) == 2 and len(result.vectors[0]) > 100
