import re

import pytest

from baseline_runner.config import EMBEDDING_PROMPTS, PROMPTS
from baseline_runner.prompts import PromptError, Prompts, render


def test_every_blank_is_filled():
    assert render("Q: {{question}} / {{context}}", question="a", context="b") == "Q: a / b"


def test_a_missing_value_is_an_error():
    with pytest.raises(PromptError):
        render("Q: {{question}} / {{context}}", question="a")


def test_an_unused_value_is_an_error():
    with pytest.raises(PromptError):
        render("Q: {{question}}", question="a", context="b")


def test_every_registered_prompt_has_its_file_version_and_blanks():
    prompts = Prompts()
    for prompt_id, row in prompts.rows.items():
        path = PROMPTS / row["file"]
        assert path.exists(), prompt_id
        assert path.stem.endswith(f"_v{row['version']}"), prompt_id
        declared = {p for p in row["placeholders"].split(";") if p}
        assert declared == set(re.findall(r"\{\{(\w+)\}\}", prompts.template(prompt_id))), prompt_id


def test_each_embedding_model_has_a_query_prompt_and_a_document_prompt():
    prompts = Prompts()
    for model_id, (query_id, document_id) in EMBEDDING_PROMPTS.items():
        assert prompts.rows[query_id]["task"] == "embed_query", model_id
        assert prompts.rows[document_id]["task"] == "embed_document", model_id


def test_prefixes_match_the_model_cards():
    prompts = Prompts()
    assert prompts.render("P05", text="x") == "search_query: x"
    assert prompts.render("P06", text="x") == "search_document: x"
    assert prompts.render("P09", text="x") == "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:x"
    assert prompts.render("P10", text="x") == "x"


def test_the_answer_prompt_asks_for_the_refusal_phrase_and_citations():
    text = Prompts().render("P01", context="[D01_x] some text", question="What?")
    assert "Insufficient knowledge." in text
    assert "square brackets" in text
    assert text.endswith("Answer:")


def test_the_scanned_page_prompt_for_the_ocr_model_starts_with_the_required_prefix():
    assert Prompts().render("P03").startswith("Text Recognition:")
