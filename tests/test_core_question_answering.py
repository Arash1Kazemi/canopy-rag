"""Test area: the question workflow on the City case study (Phase 8D), with fakes only (no model, no network).

The planted problems, end to end through retrieval, context and answer:
- Q22: N6 asks a water question whose answer is in N2. No N2 chunk reaches the model, and the answer is a refusal.
- Q01: N4 asks for the bus count. The context holds version 2 (135), never version 1 (120).
- Q06: the context holds both route documents (D11 says Route 12, D16 says Route 7), and an answer that cites both keeps both.
"""
import csv

import pytest

from rag_core.fakes import EchoLanguageModel, StubLanguageModel
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository, InMemoryVectorIndex
from rag_core.fakes import HashingEmbedder
from rag_core.rag_wiring import load_hierarchy, prepare_case_study
from rag_core.workflows.answer_prompts import load_answer_prompt
from rag_core.workflows.question_answering import QuestionService


def question(question_id):
    with open("case_study/answer_key.csv", encoding="utf-8", newline="") as handle:
        return next(r for r in csv.DictReader(handle) if r["question_id"] == question_id)


@pytest.fixture(scope="module")
def city():
    repository, index, embedder = InMemoryKnowledgeRepository(), InMemoryVectorIndex(), HashingEmbedder()
    retriever, ingested, report = prepare_case_study(repository, index, embedder, load_hierarchy())
    assert ingested and report.embedded == report.eligible
    return retriever, repository


def service(city, model, prompt="P01", **options):
    return QuestionService(city[0], model, load_answer_prompt(prompt), **options)


def test_q22_is_refused_at_n6_and_no_foreign_chunk_reaches_the_model(city):
    q = question("Q22")
    model = StubLanguageModel("Insufficient knowledge.")
    result = service(city, model).ask(q["question"], q["asked_at_node"], k=5)
    assert q["asked_at_node"] == "N6"
    assert result.answer.refused and result.answer.refusal_reason == "model_refused"
    assert result.answer.text == "Insufficient knowledge."
    n2_chunks = {c.chunk_id for c in city[1].active_chunks("N2")}
    assert n2_chunks                                              # the answer does exist in N2
    assert {h.node_id for h in result.hits} == {"N6"}
    assert n2_chunks.isdisjoint(result.answer.chunk_ids_used)
    (prompt,) = model.prompts
    context = prompt.split("Question:")[0]                          # the question itself says "chlorine"; the context must not
    assert "chlorine" not in context.lower() and "[D07_" not in context


def test_q22_cannot_be_answered_from_a_foreign_chunk_even_by_a_model_that_copies_the_context(city):
    q = question("Q22")
    result = service(city, EchoLanguageModel()).ask(q["question"], "N6", k=5)
    n6_stems = {c.location.source_stem for c in city[1].active_chunks("N6")}
    assert set(result.answer.cited_stems) <= n6_stems               # whatever it copied, it came from N6
    assert "0.2 to 0.5" not in result.answer.text                   # the N2 fact does not leak


def test_the_same_question_at_n2_reaches_the_chlorine_document(city):
    q = question("Q22")
    result = service(city, EchoLanguageModel()).ask(q["question"], "N2", k=3)
    assert any("chlorine" in h.text.lower() for h in result.hits)  # so the refusal at N6 is the node boundary


@pytest.mark.parametrize("node", ["N4"])
def test_d10_gives_135_buses_not_120(city, node):
    q = question("Q01")
    model = StubLanguageModel("The Transit Agency has 135 buses [D10_bus_fleet_inventory_v2].")
    result = service(city, model).ask(q["question"], node, k=5)
    (prompt,) = model.prompts
    assert "135" in prompt and "120" not in prompt                  # the context holds version 2 only
    assert "[D10_bus_fleet_inventory_v1]" not in prompt
    assert not result.answer.refused and "135" in result.answer.text
    assert result.answer.cited_stems == ("D10_bus_fleet_inventory_v2",)
    assert {h.version_tag for h in result.hits if h.item_id == "D10"} == {"2"}


def test_a_citation_to_the_old_version_is_removed_even_if_the_model_writes_it(city):
    q = question("Q01")
    model = StubLanguageModel("120 buses [D10_bus_fleet_inventory_v1] or 135 buses [D10_bus_fleet_inventory_v2].")
    answer = service(city, model).ask(q["question"], "N4", k=5).answer
    assert answer.invalid_citations == ("D10_bus_fleet_inventory_v1",)   # v1 was never given to the model (H09)
    assert "D10_bus_fleet_inventory_v1" not in answer.text
    assert answer.cited_stems == ("D10_bus_fleet_inventory_v2",)


def test_q06_context_holds_both_route_documents(city):
    q = question("Q06")
    model = StubLanguageModel("The sources conflict: Route 12 [D11_ridership_report_H1_2025], Route 7 [D16_passenger_survey_2025].")
    result = service(city, model, "P13").ask(q["question"], q["asked_at_node"], k=3)
    (prompt,) = model.prompts
    assert "[D11_ridership_report_H1_2025]" in prompt and "[D16_passenger_survey_2025]" in prompt
    assert "Route 12" in prompt and "Route 7" in prompt
    assert set(result.answer.cited_stems) == {"D11_ridership_report_H1_2025", "D16_passenger_survey_2025"}
    assert result.answer.prompt_id == "P13"


def test_no_hits_means_no_model_call(city):
    model = StubLanguageModel("never used")
    answer = QuestionService(city[0], model, load_answer_prompt("P01")).answer("anything", ())
    assert answer.refused and answer.refusal_reason == "no_evidence" and not answer.model_called
    assert model.prompts == []


def test_an_unknown_node_is_an_error_not_an_empty_answer(city):
    from rag_core.organization.directory import UnknownNodeError
    with pytest.raises(UnknownNodeError):
        service(city, StubLanguageModel("x")).ask("question", "N99", k=3)
