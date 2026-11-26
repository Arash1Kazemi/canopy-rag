"""The answer use case (Phase 8C): hits and a question in, a checked answer out.

The steps, in order:
1. Assemble the context from the ranked hits within the token budget (context.py).
2. No usable context: return "Insufficient knowledge." and do NOT call the model.
3. Render the prompt, call the model, read the reply.
4. The model refused in its own words: return the fixed refusal. The reply is kept in raw_text only.
5. Check every citation against the chunks that were given (H09). A citation to anything else is removed from the text
   and listed as invalid.
6. No valid citation left: by default the answer becomes "Insufficient knowledge." (H09: every answer has a citation or
   refuses). With uncited_policy="mark" the text is kept and flagged `uncited` instead (decision A37, to confirm).

This module is pure: it takes the model and the prompt text as arguments and reads no file.
"""
import re
from dataclasses import dataclass
from typing import Optional

from ..shared.kernel import DomainError
from .citation import check_citations
from .context import (DEFAULT_ANSWER_TOKENS, DEFAULT_MODEL_CONTEXT_TOKENS, assemble_context, context_budget)

REFUSAL_PHRASE = "insufficient knowledge"     # the Phase 2 phrase (baseline_runner/config.py)
REFUSAL_TEXT = "Insufficient knowledge."
BLANK = re.compile(r"\{\{(\w+)\}\}")
UNCITED_POLICIES = ("refuse", "mark")

# why an answer is a refusal
NO_EVIDENCE = "no_evidence"             # nothing to put in the context; the model was not called
CONTEXT_TOO_SMALL = "context_too_small"  # hits existed, but not even the first one fitted; the model was not called
MODEL_REFUSED = "model_refused"          # the model said "insufficient knowledge" itself
NO_VALID_CITATION = "no_valid_citation"  # the model answered, but cited nothing that was given (H09)


def says_refusal(text):
    """The phrase check of the baseline: the reply contains "insufficient knowledge", in any case and spacing."""
    return REFUSAL_PHRASE in " ".join(text.lower().split())


@dataclass(frozen=True)
class AnswerPrompt:
    """A versioned answer prompt: its registry id (P01, P13), its version, and the template text with the blanks
    {{context}} and {{question}}. The text comes from prompts/ (workflows/answer_prompts.py loads it)."""
    prompt_id: str
    version: int
    template: str

    def __post_init__(self):
        blanks = set(BLANK.findall(self.template))
        if blanks != {"context", "question"}:
            raise DomainError(f"an answer prompt has the blanks context and question, not {sorted(blanks)}")

    def render(self, context, question):
        """Fill the blanks in one pass, so text inside the context that looks like {{a blank}} is never filled."""
        values = {"context": context, "question": question}
        return BLANK.sub(lambda m: values[m.group(1)], self.template)

    def fixed_text(self):
        """The prompt without the context: what the budget must leave room for (the question is added by the caller)."""
        return BLANK.sub("", self.template)


@dataclass(frozen=True)
class Answer:
    text: str                  # what the user sees: the checked answer, or the fixed refusal
    refused: bool
    refusal_reason: str        # "" when not refused; else one of the four reasons above
    citations: tuple           # Citation objects: one per given chunk of every validly cited stem (chunk, pages, headings)
    invalid_citations: tuple   # stems the model cited that were not in the context (already removed from `text`)
    uncited: bool              # True only with uncited_policy="mark": an answer that kept no valid citation
    prompt_id: str
    prompt_version: int
    chunk_ids_used: tuple      # the chunks that were in the context, in rank order
    chunk_ids_omitted: tuple   # hits that were left out (blank, repeated, below min score, over budget)
    model_called: bool
    raw_text: str              # the model's reply as it came; "" when the model was not called
    budget_tokens: int
    context_tokens: int        # estimated tokens of the context that was given

    @property
    def cited_stems(self):
        """The valid file stems the answer cites, each once, in the order the answer first cites them."""
        return tuple(dict.fromkeys(c.source_stem for c in self.citations))


def _refusal(prompt, context, reason, raw="", called=False, invalid=()):
    return Answer(REFUSAL_TEXT, True, reason, (), tuple(invalid), False, prompt.prompt_id, prompt.version,
                  context.chunk_ids, tuple(o.chunk_id for o in context.omitted), called, raw,
                  context.budget_tokens, context.estimated_tokens)


def answer_question(question, hits, model, prompt, *, model_context_tokens=DEFAULT_MODEL_CONTEXT_TOKENS,
                    answer_tokens=DEFAULT_ANSWER_TOKENS, budget_tokens: Optional[int] = None, min_score=None,
                    uncited_policy="refuse"):
    """Answer one question from ranked hits (best first). `hits` are ContextHit objects of the asking node only: the
    retrieval step already filtered by node and active version (H01); this function checks the citations, not the node.

    model_context_tokens and answer_tokens set the budget (see context_budget); pass budget_tokens to fix it directly.
    The result is deterministic when the model is."""
    if not question or not question.strip():
        raise DomainError("a question cannot be empty")
    if uncited_policy not in UNCITED_POLICIES:
        raise DomainError(f"uncited_policy is one of {UNCITED_POLICIES}, not {uncited_policy!r}")
    hits = tuple(hits)
    if budget_tokens is None:
        budget_tokens = context_budget(model_context_tokens, answer_tokens, prompt.fixed_text() + " " + question)
    context = assemble_context(hits, budget_tokens, min_score)

    if context.is_empty:
        usable = [o for o in context.omitted if o.reason == "over_budget"]
        return _refusal(prompt, context, CONTEXT_TOO_SMALL if usable else NO_EVIDENCE)

    raw = model.generate(prompt.render(context.text, question))
    if says_refusal(raw):
        return _refusal(prompt, context, MODEL_REFUSED, raw, True)

    check = check_citations(raw, context.stems)
    if not check.valid_stems:
        if uncited_policy == "refuse":
            return _refusal(prompt, context, NO_VALID_CITATION, raw, True, check.invalid_stems)
        uncited = True
    else:
        uncited = False
    citations = tuple(h.citation() for stem in check.valid_stems for h in context.given if h.source_stem == stem)
    return Answer(check.cleaned_text, False, "", citations, check.invalid_stems, uncited, prompt.prompt_id, prompt.version,
                  context.chunk_ids, tuple(o.chunk_id for o in context.omitted), True, raw,
                  context.budget_tokens, context.estimated_tokens)
