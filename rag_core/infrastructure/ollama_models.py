"""Ollama behind the VisionModel port. It reuses the Phase 2 client, which talks only to 127.0.0.1 (H06)."""
import base64
from pathlib import Path

from baseline_runner.config import PAGE_OPTIONS, PROMPTS
from baseline_runner.ollama_api import OllamaClient

# glm-ocr is the baseline LVM (docs/baseline_report.md). Its model card says the prompt is "Text Recognition:" (P03).
DEFAULT_LVM_TAG = "glm-ocr:q8_0"
DEFAULT_PROMPT_FILE = PROMPTS / "read_scanned_page_glm_v1.txt"


class OllamaVisionModel:
    def __init__(self, model_tag=DEFAULT_LVM_TAG, prompt=None, client=None):
        self.model_tag = model_tag
        self.prompt = prompt if prompt is not None else Path(DEFAULT_PROMPT_FILE).read_text(encoding="utf-8").strip()
        self.client = client or OllamaClient()

    def read_page(self, png):
        image = base64.b64encode(png).decode("ascii")
        reply = self.client.chat(self.model_tag, [{"role": "user", "content": self.prompt}], images=[image], options=PAGE_OPTIONS)
        return reply.text
