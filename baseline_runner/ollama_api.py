"""A small client for the local Ollama server. Standard library only.

The HTTP call is one replaceable function (`transport`), so tests can feed the client canned replies
without any network.
"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import GENERATION_OPTIONS, OLLAMA_URL

NANOSECONDS = 1e9


class OllamaError(RuntimeError):
    pass


@dataclass
class Stats:
    """Timings from one reply, in seconds and tokens. Ollama reports durations in nanoseconds."""

    total_s: float = 0.0
    load_s: float = 0.0
    prompt_tokens: int = 0
    prompt_s: float = 0.0
    generated_tokens: int = 0
    generated_s: float = 0.0

    @property
    def ttft_s(self):
        """Time before the first generated token: loading the model plus reading the prompt.
        This is an estimate from Ollama's own timings, because we do not stream the reply."""
        return self.load_s + self.prompt_s

    @property
    def tokens_per_s(self):
        return self.generated_tokens / self.generated_s if self.generated_s > 0 else 0.0


@dataclass
class ChatResult:
    text: str
    stats: Stats
    thinking: str = ""


@dataclass
class EmbedResult:
    vectors: list
    stats: Stats


def stats_from(reply):
    return Stats(
        total_s=reply.get("total_duration", 0) / NANOSECONDS,
        load_s=reply.get("load_duration", 0) / NANOSECONDS,
        prompt_tokens=reply.get("prompt_eval_count", 0),
        prompt_s=reply.get("prompt_eval_duration", 0) / NANOSECONDS,
        generated_tokens=reply.get("eval_count", 0),
        generated_s=reply.get("eval_duration", 0) / NANOSECONDS,
    )


class OllamaClient:
    def __init__(self, base_url=OLLAMA_URL, timeout=900, transport=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport or self._http

    def _http(self, method, path, payload):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            raise OllamaError(f"HTTP {error.code} from {path}: {body}") from error
        except urllib.error.URLError as error:
            raise OllamaError(f"cannot reach Ollama at {self.base_url}: {error.reason}") from error

    def version(self):
        return self._transport("GET", "/api/version", None).get("version", "unknown")

    def models(self):
        """Pulled models: tag -> digest."""
        reply = self._transport("GET", "/api/tags", None)
        return {m.get("name", ""): m.get("digest", "") for m in reply.get("models", [])}

    def embed(self, model, texts, *, keep_alive="5m"):
        # truncate=False makes a too-long input an error instead of silently cutting it
        payload = {"model": model, "input": list(texts), "truncate": False, "keep_alive": keep_alive}
        reply = self._transport("POST", "/api/embed", payload)
        vectors = reply.get("embeddings")
        if not vectors or len(vectors) != len(texts):
            raise OllamaError(f"{model} returned {0 if not vectors else len(vectors)} vectors for {len(texts)} texts")
        return EmbedResult(vectors, stats_from(reply))

    def chat(self, model, messages, *, images=None, options=None, think=None, json_mode=False, keep_alive="5m"):
        """One question, one reply. `images` are base64 strings. An option set to None is dropped."""
        merged = {k: v for k, v in {**GENERATION_OPTIONS, **(options or {})}.items() if v is not None}
        sent = [dict(m) for m in messages]
        if images:
            sent[-1]["images"] = list(images)
        payload = {"model": model, "messages": sent, "stream": False, "options": merged, "keep_alive": keep_alive}
        if json_mode:
            payload["format"] = "json"
        if think is not None:
            payload["think"] = think
        try:
            reply = self._transport("POST", "/api/chat", payload)
        except OllamaError as error:
            if think is None or "think" not in str(error).lower():
                raise
            payload.pop("think")  # this model has no thinking mode: ask again without the setting
            reply = self._transport("POST", "/api/chat", payload)
        message = reply.get("message", {})
        return ChatResult(text=message.get("content") or "", thinking=message.get("thinking") or "", stats=stats_from(reply))
