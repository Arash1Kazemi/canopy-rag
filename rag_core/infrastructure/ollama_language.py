"""Ollama behind the LanguageModel port. It reuses the Phase 2 client, which talks only to 127.0.0.1:11500 (H06).

phi4-mini is the baseline LLM (docs/baseline_report.md). The Phase 2 settings are kept (temperature 0, seed 42), so a
rerun gives the same reply; only the reply length is raised, because a list of sub-issues is longer than an answer.
"""
from baseline_runner.ollama_api import OllamaClient

DEFAULT_LLM_TAG = "phi4-mini:3.8b"
SUGGESTION_OPTIONS = {"num_predict": 512}


class OllamaLanguageModel:
    def __init__(self, model_tag=DEFAULT_LLM_TAG, client=None, options=None):
        self.model_tag = model_tag
        self.client = client or OllamaClient()
        self.options = dict(SUGGESTION_OPTIONS if options is None else options)

    def generate(self, prompt):
        reply = self.client.chat(self.model_tag, [{"role": "user", "content": prompt}], options=self.options)
        return reply.text
