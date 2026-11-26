"""Ollama behind the EmbeddingModel port (Phase 8A). qwen3-embedding 0.6b is the baseline embedding model.

It reuses the Phase 2 client and the Phase 2 prompt files, so a vector here is the vector the baseline made:
- a chunk is sent as it is (P10, embed_document_plain_v1.txt: the qwen3 model card puts no instruction on documents);
- a question is sent as "Instruct: ...\\nQuery:<question>" (P09, embed_query_qwen3_v1.txt).

H06: the server must be on this machine. The address is http://127.0.0.1:11500 (Windows reserved Ollama's default
port), and RAG_OLLAMA_URL may change the port but never the host: any address that is not loopback is refused.
"""
import os
from urllib.parse import urlparse

from baseline_runner.config import EMBEDDING_PROMPTS, OLLAMA_URL
from baseline_runner.ollama_api import OllamaClient
from baseline_runner.prompts import Prompts

DEFAULT_EMBEDDING_ID = "qwen3-embedding-0.6b"       # the model id in models/model_registry.csv
DEFAULT_EMBEDDING_TAG = "qwen3-embedding:0.6b"      # its Ollama runtime tag
URL_VARIABLE = "RAG_OLLAMA_URL"
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def ollama_url(environ=None):
    """The local Ollama address: RAG_OLLAMA_URL when set, else the project default. Never another machine (H06)."""
    url = (environ if environ is not None else os.environ).get(URL_VARIABLE) or OLLAMA_URL
    host = urlparse(url).hostname
    if host not in LOOPBACK:
        raise ValueError(f"H06: Ollama must run on this machine (127.0.0.1), not at {url}")
    return url


class OllamaEmbeddingModel:
    def __init__(self, model_tag=DEFAULT_EMBEDDING_TAG, model_id=DEFAULT_EMBEDDING_ID, client=None, prompts=None):
        self.model_tag = model_tag
        self.query_prompt, self.document_prompt = EMBEDDING_PROMPTS[model_id]
        self.prompts = prompts or Prompts()
        self.client = client or OllamaClient(base_url=ollama_url())

    def embed(self, texts):
        texts = list(texts)
        if not texts:
            return []
        rendered = [self.prompts.render(self.document_prompt, text=t) for t in texts]
        return self.client.embed(self.model_tag, rendered).vectors

    def embed_query(self, text):
        return self.client.embed(self.model_tag, [self.prompts.render(self.query_prompt, text=text)]).vectors[0]
