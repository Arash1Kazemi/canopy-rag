"""Test area: the Ollama language-model adapter (Phase 8D). A fake HTTP layer stands in for the server; no network.

Pinned: the Phase 2 settings are kept when options={} is passed, thinking can be switched off, and the timings of the
latest reply are kept in `last_stats` so an evaluation can record M22 to M24. EchoLanguageModel (the --fake-models model)
cites the first chunk of the context, or refuses when there is none.
"""
from baseline_runner.ollama_api import OllamaClient
from rag_core.fakes import EchoLanguageModel
from rag_core.infrastructure.ollama_language import OllamaLanguageModel


class FakeHttp:
    def __init__(self):
        self.calls = []

    def __call__(self, method, path, payload):
        self.calls.append(payload)
        return {"message": {"content": "135 buses [D10_bus_fleet_inventory_v2]"}, "total_duration": 2_000_000_000,
                "load_duration": 500_000_000, "prompt_eval_duration": 250_000_000, "prompt_eval_count": 300,
                "eval_count": 20, "eval_duration": 500_000_000}


def test_empty_options_keep_the_phase_2_settings_and_record_the_timings():
    http = FakeHttp()
    model = OllamaLanguageModel("phi4-mini:3.8b", client=OllamaClient(transport=http), options={})
    assert model.generate("prompt") == "135 buses [D10_bus_fleet_inventory_v2]"
    (payload,) = http.calls
    assert payload["options"] == {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 256}
    assert "think" not in payload
    assert model.last_stats.ttft_s == 0.75 and model.last_stats.tokens_per_s == 40 and model.last_stats.prompt_tokens == 300


def test_thinking_can_be_switched_off_and_the_default_reply_length_is_unchanged_for_issues():
    http = FakeHttp()
    OllamaLanguageModel("qwen3:1.7b", client=OllamaClient(transport=http), options={}, think=False).generate("p")
    assert http.calls[0]["think"] is False
    OllamaLanguageModel(client=OllamaClient(transport=http)).generate("p")      # the Phase 7 default
    assert http.calls[1]["options"]["num_predict"] == 512


def test_the_echo_model_cites_the_first_chunk_or_refuses():
    model = EchoLanguageModel()
    reply = model.generate("Rules...\n\nDocuments:\n[D10_x] The fleet has 135 buses.\n\n[D13_y] Other.\n\nQuestion: how many?\n\nAnswer:")
    assert reply == "The fleet has 135 buses. [D10_x]"
    assert model.generate("Documents:\n\nQuestion: q\n\nAnswer:") == "Insufficient knowledge."
    assert len(model.prompts) == 2
