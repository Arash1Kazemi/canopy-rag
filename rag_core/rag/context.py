"""Context assembly: from ranked hits to the text that goes into the answer prompt (Phase 8C).

Retrieval returns hits in rank order. This module fills the context in that order until the budget is used. A chunk is
never cut: it goes in whole or it stays out, and the result says which. The format of one entry is the Phase 2 format,
"[file stem] chunk text" with a blank line between entries, so results stay comparable with the 2026-10-28 baseline.

The budget is counted in estimated tokens (decision A36): there is no tokenizer in the core, and the real count depends
on the model. The estimate errs on the high side, so the prompt is less likely to overrun the model's context window.
"""
import math
from dataclasses import dataclass
from typing import Optional

from ..shared.kernel import DomainError
from .citation import STEM, Citation

TOKENS_PER_WORD = 1.5    # the Phase 2 prompts measured about 1.25 tokens per word; 1.5 leaves a margin
CHARS_PER_TOKEN = 3.0    # ids and numbers split into many small tokens, so a word count alone can be too low
DEFAULT_MODEL_CONTEXT_TOKENS = 4096   # num_ctx of the Phase 2 baseline (baseline_runner/config.py)
DEFAULT_ANSWER_TOKENS = 256           # num_predict of the Phase 2 baseline


def estimate_tokens(text):
    """About how many tokens a text takes: the larger of the word-based and the character-based estimate."""
    return max(math.ceil(len(text.split()) * TOKENS_PER_WORD), math.ceil(len(text) / CHARS_PER_TOKEN))


@dataclass(frozen=True)
class ContextHit:
    """One ranked chunk as the answer step needs it. The retrieval step returns the chunk id, score and location; the
    wiring loads the chunk text and builds this object (ContextHit.of_chunk does it for a KnowledgeChunk)."""
    chunk_id: str
    text: str
    source_stem: str
    score: Optional[float] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    heading_path: tuple = ()

    def __post_init__(self):
        if not self.chunk_id:
            raise DomainError("a context hit needs a chunk id")
        if not STEM.fullmatch(self.source_stem or ""):
            raise DomainError(f"a context hit names a file stem with letters, digits, '.', '_' or '-', not {self.source_stem!r}")

    @classmethod
    def of_chunk(cls, chunk, score=None):
        loc = chunk.location
        return cls(chunk.chunk_id, chunk.text, loc.source_stem, score, loc.page_start, loc.page_end, loc.heading_path)

    def citation(self):
        return Citation(self.source_stem, self.chunk_id, self.page_start, self.page_end, self.heading_path)

    def entry(self):
        """How the chunk looks inside the prompt (the Phase 2 form)."""
        return f"[{self.source_stem}] {self.text}"


@dataclass(frozen=True)
class Omitted:
    chunk_id: str
    reason: str   # "blank", "repeated", "below_min_score" or "over_budget"


@dataclass(frozen=True)
class AssembledContext:
    text: str
    given: tuple             # the ContextHit objects in the text, in rank order
    omitted: tuple           # Omitted records: every hit that was left out, and why
    budget_tokens: int
    estimated_tokens: int

    @property
    def chunk_ids(self):
        return tuple(h.chunk_id for h in self.given)

    @property
    def stems(self):
        """The file stems in the context, each once, in rank order. A citation must be one of these (H09)."""
        return tuple(dict.fromkeys(h.source_stem for h in self.given))

    @property
    def is_empty(self):
        return not self.given


def context_budget(model_context_tokens=DEFAULT_MODEL_CONTEXT_TOKENS, answer_tokens=DEFAULT_ANSWER_TOKENS, fixed_text=""):
    """Tokens left for the chunks: the model's window, minus room for the reply, minus the prompt text that is not
    context (the template and the question, passed as `fixed_text`). Never below zero."""
    return max(0, model_context_tokens - answer_tokens - estimate_tokens(fixed_text))


def assemble_context(hits, budget_tokens, min_score=None):
    """Fill the context from ranked hits, best first, within budget_tokens.

    A hit is left out (and recorded) when its text is blank, when its chunk id came earlier, when its score is below
    min_score (no default: a number needs a source), or when it does not fit. The first chunk that does not fit ends
    the filling: a lower-ranked chunk never takes the place of a higher-ranked one that was too big. An entry costs
    the estimated tokens of its text."""
    if budget_tokens < 0:
        raise DomainError("the context budget cannot be negative")
    given, omitted, seen = [], [], set()
    used = 0
    full = False
    for hit in hits:
        if hit.chunk_id in seen:
            omitted.append(Omitted(hit.chunk_id, "repeated"))
        elif not hit.text.strip():
            omitted.append(Omitted(hit.chunk_id, "blank"))
        elif min_score is not None and hit.score is not None and hit.score < min_score:
            omitted.append(Omitted(hit.chunk_id, "below_min_score"))
        elif full:
            omitted.append(Omitted(hit.chunk_id, "over_budget"))
        else:
            cost = estimate_tokens(hit.entry())
            if used + cost > budget_tokens:
                full = True
                omitted.append(Omitted(hit.chunk_id, "over_budget"))
            else:
                given.append(hit)
                used += cost
        seen.add(hit.chunk_id)
    text = "\n\n".join(h.entry() for h in given)
    return AssembledContext(text, tuple(given), tuple(omitted), budget_tokens, used)
