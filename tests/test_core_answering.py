"""Test area: Answers and citations (the answer use case, H09, Phase 8C)."""
from pathlib import Path

import pytest

from rag_core.fakes import StubLanguageModel
from rag_core.knowledge.model import KnowledgeChunk, KnowledgeItemId, SourceLocation, VersionTag
from rag_core.rag.answering import (CONTEXT_TOO_SMALL, MODEL_REFUSED, NO_EVIDENCE, NO_VALID_CITATION, REFUSAL_TEXT,
                                    AnswerPrompt, answer_question, says_refusal)
from rag_core.rag.citation import check_citations
from rag_core.rag.context import ContextHit
from rag_core.shared.kernel import DomainError
from rag_core.workflows.answer_prompts import load_answer_prompt

D10 = "D10_bus_fleet_inventory_v2"
D11 = "D11_ridership_report_2025"
D16 = "D16_passenger_survey_2025"
D19 = "D19_meeting_minutes_2025-06-18"
PROMPT = load_answer_prompt("P01")


def hit(chunk_id, stem, text, **kw):
    return ContextHit(chunk_id, text, stem, **kw)


FLEET = hit("D10@2#1", D10, "The fleet has 135 buses.")


def ask(reply, hits=(FLEET,), question="How many buses?", prompt=PROMPT, **kw):
    model = StubLanguageModel(reply)
    return answer_question(question, hits, model, prompt, **kw), model


# ---------------------------------------------------------------- refusal without evidence (Q22-style)
def test_no_hits_means_insufficient_knowledge_and_the_model_is_not_called():
    answer, model = ask("Chlorine is 0.2 mg/L.", hits=[], question="What is the allowed chlorine residual?")
    assert answer.refused and answer.text == REFUSAL_TEXT and answer.refusal_reason == NO_EVIDENCE
    assert model.prompts == [] and answer.model_called is False and answer.raw_text == ""
    assert answer.citations == () and answer.chunk_ids_used == ()


def test_hits_that_are_all_filtered_out_are_treated_as_no_evidence():
    answer, model = ask("x", hits=[hit("a#1", D10, "  "), hit("a#2", D10, "weak", score=0.1)], min_score=0.5)
    assert answer.refusal_reason == NO_EVIDENCE and model.prompts == []
    assert answer.chunk_ids_omitted == ("a#1", "a#2")


def test_a_context_where_not_even_the_first_chunk_fits_is_refused_with_its_own_reason_and_no_model_call():
    answer, model = ask("x", budget_tokens=3)
    assert answer.refused and answer.refusal_reason == CONTEXT_TOO_SMALL and model.prompts == []
    assert answer.chunk_ids_omitted == ("D10@2#1",)


# ---------------------------------------------------------------- the model's own refusal
@pytest.mark.parametrize("reply", ["Insufficient knowledge.", "insufficient  knowledge", "INSUFFICIENT\nKNOWLEDGE to say."])
def test_the_models_refusal_is_detected_the_way_the_baseline_did(reply):
    assert says_refusal(reply)
    answer, _ = ask(reply)
    assert answer.refused and answer.refusal_reason == MODEL_REFUSED and answer.model_called


def test_a_model_refusal_shows_only_the_fixed_phrase_and_never_leaks_the_rest_of_the_reply():
    answer, _ = ask(f"Insufficient knowledge. Though the budget might be 5 million [{D10}].")
    assert answer.text == REFUSAL_TEXT and answer.citations == ()
    assert "5 million" in answer.raw_text                   # kept for a person who debugs, never shown as the answer


def test_a_normal_answer_is_not_taken_for_a_refusal():
    assert not says_refusal(f"The fleet has 135 buses [{D10}].")


# ---------------------------------------------------------------- citations are checked against the context (H09)
def test_a_valid_citation_is_kept_with_its_chunk():
    answer, _ = ask(f"The fleet has 135 buses [{D10}].")
    assert not answer.refused and answer.text == f"The fleet has 135 buses [{D10}]."
    assert answer.cited_stems == (D10,) and answer.invalid_citations == ()
    assert [c.chunk_id for c in answer.citations] == ["D10@2#1"]


def test_a_citation_to_a_file_that_was_not_given_is_removed_and_listed():
    answer, _ = ask(f"The fleet has 135 buses [{D10}]. The budget is 5 million [D20_cost_estimate].")
    assert answer.cited_stems == (D10,)
    assert answer.invalid_citations == ("D20_cost_estimate",)
    assert "D20_cost_estimate" not in answer.text and answer.text == f"The fleet has 135 buses [{D10}]. The budget is 5 million."


def test_the_old_version_of_a_file_is_invalid_when_only_the_new_one_was_given():
    answer, _ = ask("The fleet has 120 buses [D10_bus_fleet_inventory_v1].")
    assert answer.refused and answer.refusal_reason == NO_VALID_CITATION
    assert answer.invalid_citations == ("D10_bus_fleet_inventory_v1",)


def test_an_answer_with_no_valid_citation_becomes_insufficient_knowledge_by_default():
    for reply in ("The fleet has 135 buses.", "The fleet has 135 buses [D99_made_up]."):
        answer, _ = ask(reply)
        assert answer.refused and answer.text == REFUSAL_TEXT and answer.refusal_reason == NO_VALID_CITATION
        assert answer.raw_text == reply and answer.model_called


def test_the_mark_policy_keeps_an_uncited_answer_and_flags_it():
    answer, _ = ask("The fleet has 135 buses [D99_made_up].", uncited_policy="mark")
    assert not answer.refused and answer.uncited and answer.citations == ()
    assert answer.text == "The fleet has 135 buses." and answer.invalid_citations == ("D99_made_up",)
    assert not ask(f"135 buses [{D10}].", uncited_policy="mark")[0].uncited


def test_an_unknown_policy_is_an_error():
    with pytest.raises(DomainError):
        ask("x", uncited_policy="ignore")


def test_a_file_extension_after_the_stem_is_tolerated_and_written_as_given():
    answer, _ = ask(f"135 buses [{D10}.md].")
    assert answer.cited_stems == (D10,) and answer.text == f"135 buses [{D10}]."


def test_a_pdf_citation_keeps_its_page_numbers_and_the_long_form_shows_them():
    loc = SourceLocation(KnowledgeItemId("D19"), VersionTag("1"), f"N6_bus_network_project/{D19}.pdf", 0, 60, 1, 1, ())
    chunk = KnowledgeChunk("D19@1#2", "N6", 2, "Decision: add 5 buses on Route 7.", loc)
    answer, _ = ask(f"The council decided to add 5 buses [{D19}].", hits=[ContextHit.of_chunk(chunk, 0.8)], question="What was decided?")
    assert answer.citations[0].page_start == 1 and answer.citations[0].page_end == 1
    assert answer.citations[0].render_long() == f"[{D19}, p. 1, chunk D19@1#2]"


def test_every_given_chunk_of_a_cited_file_is_listed_because_the_answer_cites_the_file_not_the_chunk():
    hits = [hit("D10@2#1", D10, "Fleet is 135.", page_start=1, page_end=1), hit("D10@2#2", D10, "Age is 9 years.", page_start=2, page_end=2)]
    answer, _ = ask(f"135 buses [{D10}].", hits=hits)
    assert [c.chunk_id for c in answer.citations] == ["D10@2#1", "D10@2#2"] and answer.cited_stems == (D10,)


# ---------------------------------------------------------------- Q06: a conflict between two documents
Q06_HITS = [hit("D11@1#1", D11, "Route 12 is the busiest route: 2.9 million trips, 19 percent."),
            hit("D16@1#1", D16, "41 percent of respondents say Route 7 is the busiest.")]


def test_the_v2_prompt_tells_the_model_to_report_a_conflict_and_v1_does_not():
    v1, v2 = load_answer_prompt("P01"), load_answer_prompt("P13")
    assert (v1.prompt_id, v1.version, v2.prompt_id, v2.version) == ("P01", 1, "P13", 2)
    assert "disagree" not in v1.template and "disagree" in v2.template and "both" in v2.template
    assert "Insufficient knowledge." in v2.template                       # the refusal sentence is unchanged


def test_a_q06_answer_that_names_both_routes_keeps_both_citations():
    v2 = load_answer_prompt("P13")
    reply = f"The documents disagree: Route 12 [{D11}] versus Route 7 [{D16}]."
    answer, model = ask(reply, hits=Q06_HITS, question="Which route is the busiest?", prompt=v2)
    assert answer.cited_stems == (D11, D16) and answer.prompt_id == "P13" and answer.prompt_version == 2
    sent = model.prompts[0]
    assert "Route 12" in sent and "Route 7" in sent and sent.index(f"[{D11}]") < sent.index(f"[{D16}]")
    assert "report both answers" in sent


# ---------------------------------------------------------------- the prompt, the budget and determinism
def test_the_prompt_id_and_version_are_recorded_on_every_kind_of_answer():
    for reply, hits in ((f"135 [{D10}]", (FLEET,)), ("Insufficient knowledge.", (FLEET,)), ("x", ())):
        answer, _ = ask(reply, hits=hits)
        assert (answer.prompt_id, answer.prompt_version) == ("P01", 1)


def test_the_prompt_sent_to_the_model_is_the_template_with_context_and_question_filled():
    _, model = ask(f"135 [{D10}]")
    expected = PROMPT.template.replace("{{context}}", f"[{D10}] The fleet has 135 buses.").replace("{{question}}", "How many buses?")
    assert model.prompts == [expected]


def test_text_in_the_context_that_looks_like_a_blank_is_not_filled_in():
    tricky = hit("D10@2#1", D10, "Note: {{question}} is a placeholder.")
    _, model = ask(f"x [{D10}]", hits=[tricky], question="How many buses?")
    assert "Note: {{question}} is a placeholder." in model.prompts[0]


def test_the_budget_follows_the_model_window_and_the_chunks_that_fit_are_the_ones_given():
    hits = [hit(f"D10@2#{n}", D10, " ".join(["word"] * 80)) for n in range(1, 8)]
    small, _ = ask(f"x [{D10}]", hits=hits, model_context_tokens=900, answer_tokens=256)
    large, _ = ask(f"x [{D10}]", hits=hits, model_context_tokens=4096, answer_tokens=256)
    assert 0 < len(small.chunk_ids_used) < len(large.chunk_ids_used) == 7
    assert small.context_tokens <= small.budget_tokens < large.budget_tokens
    assert small.chunk_ids_used + small.chunk_ids_omitted == tuple(h.chunk_id for h in hits)


def test_an_explicit_budget_overrides_the_derived_one():
    answer, _ = ask(f"x [{D10}]", budget_tokens=500)
    assert answer.budget_tokens == 500


def test_the_same_input_gives_the_same_answer_every_time():
    runs = [ask(f"135 buses [{D10}]. Also [D20_x].", hits=Q06_HITS + [FLEET])[0] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_an_empty_question_is_an_error():
    with pytest.raises(DomainError):
        ask("x", question="  ")


def test_an_answer_prompt_needs_exactly_the_blanks_context_and_question():
    with pytest.raises(DomainError):
        AnswerPrompt("PX", 1, "Question: {{question}}")
    with pytest.raises(DomainError):
        AnswerPrompt("PX", 1, "{{context}} {{question}} {{extra}}")


def test_loading_a_prompt_that_is_not_an_answer_prompt_or_does_not_exist_fails():
    with pytest.raises(DomainError):
        load_answer_prompt("P12")
    with pytest.raises(DomainError):
        load_answer_prompt("P99")


def test_the_loaded_v1_prompt_is_the_file_without_its_final_newline():
    text = Path("prompts/answer_with_citations_v1.txt").read_text(encoding="utf-8")
    assert PROMPT.template == text[:-1]


# ---------------------------------------------------------------- check_citations on its own
def test_check_citations_splits_valid_from_invalid_and_cleans_the_text():
    check = check_citations(f"A [{D10}, D99_x]. B [D98_y]. C [the report above].", [D10])
    assert check.valid_stems == (D10,) and check.invalid_stems == ("D99_x", "D98_y")
    assert check.cleaned_text == f"A [{D10}]. B. C [the report above]."


def test_check_citations_leaves_an_answer_without_removals_exactly_as_it_was():
    text = f"A  [{D10}] ,  b.\n\nC."
    assert check_citations(text, [D10]).cleaned_text == text


def test_check_citations_keeps_a_non_stem_part_of_a_mixed_bracket():
    assert check_citations("A [D99_x, see above].", [D10]).cleaned_text == "A [see above]."
