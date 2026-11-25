"""Paths and fixed settings. Everything a result depends on is here, so a result can be repeated."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CASE = PROJECT / "case_study"
METRICS = PROJECT / "metrics"
PROMPTS = PROJECT / "prompts"
REGISTRY = PROJECT / "models" / "model_registry.csv"
JUDGE_PROBE = PROJECT / "experiments" / "judge_probe.csv"
RESULTS = PROJECT / "results"

# The server listens on this machine only. Nothing in the runner calls any other address.
OLLAMA_URL = "http://127.0.0.1:11500"  # not Ollama's default 11434: Windows reserved it (see scripts/start_ollama.ps1)

# The same settings for every model, so a difference in results is not a difference in settings.
GENERATION_OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 256}
PAGE_OPTIONS = {"num_predict": 1024}  # reading a page needs a longer reply than answering a question

REFUSAL_PHRASE = "insufficient knowledge"

# chunk setting name -> (words per chunk, words of overlap). None means one chunk per file.
CHUNK_CONFIGS = {"file": None, "words80": (80, 15)}
BASELINE_CHUNKS = "words80"  # the simplest usual setting, so it is the baseline
# Chunk settings cut by the core's chunking policies (rag_core/knowledge/chunking.py), for the Phase 4 E3 comparison
# of words80 with sections80. E1 does not try them unless asked.
CORE_CHUNKS = ("sections80",)
BASELINE_K = 3
KS = (1, 3, 5)
LATENCY_KS = (1, 3, 6, 12)
LATENCY_QUESTIONS = ("Q06", "Q12", "Q25")  # questions that need more than one chunk

# embedding model id -> (query prompt id, document prompt id)
EMBEDDING_PROMPTS = {
    "nomic-embed-text": ("P05", "P06"),
    "embeddinggemma-300m": ("P07", "P08"),
    "qwen3-embedding-0.6b": ("P09", "P10"),
    "bge-m3": ("P11", "P10"),
}
DEFAULT_READ_PAGE_PROMPT = "P02"
READ_PAGE_PROMPTS = {"glm-ocr-q8": "P03"}
