"""The question workflow (Phase 8D): retrieve inside one node, then answer from what was retrieved.

It joins the two use cases of Phase 8: `Retriever` (8B, node filter before ranking) and `answer_question` (8C, context
budget and citation check). It takes both ports and the prompt as arguments and reads no file, so a unit test can pass
a HashingEmbedder-backed retriever and a StubLanguageModel.

`retrieve` and `answer` are public on their own because the evaluation retrieves for every question first and answers
afterwards: on a small GPU the embedding model and the language model should not be swapped in and out per question.
"""
from dataclasses import dataclass
from typing import Optional

from ..rag.answering import Answer, answer_question
from ..rag.context import ContextHit
from ..rag.retrieval import DEFAULT_K


@dataclass(frozen=True)
class AskResult:
    question: str
    node_id: str
    k: int
    hits: tuple        # RetrievalHit objects, best first: everything retrieval returned
    answer: Answer     # what was given to the model is answer.chunk_ids; the rest is in answer.chunk_ids_omitted


class QuestionService:
    """QuestionService(retriever, model, prompt).ask(question, node_id) -> AskResult.

    `answer_options` are passed to `answer_question` (model_context_tokens, answer_tokens, budget_tokens, min_score,
    uncited_policy)."""

    def __init__(self, retriever, model, prompt, **answer_options):
        self.retriever = retriever
        self.model = model
        self.prompt = prompt
        self.answer_options = answer_options

    def retrieve(self, question, node_id, k=DEFAULT_K, metadata: Optional[dict] = None):
        return tuple(self.retriever.retrieve(question, node_id, k, metadata))

    def answer(self, question, hits):
        context_hits = [ContextHit.of_chunk(h.chunk, h.score) for h in hits]
        return answer_question(question, context_hits, self.model, self.prompt, **self.answer_options)

    def ask(self, question, node_id, k=DEFAULT_K, metadata: Optional[dict] = None):
        hits = self.retrieve(question, node_id, k, metadata)
        return AskResult(question, str(node_id), k, hits, self.answer(question, hits))
