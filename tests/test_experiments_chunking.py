"""E3 with the two chunking policies of Phase 4 (architecture/chunking_spec.md): words80 (the Phase 2 baseline) and
sections80 (windows that stop at headings). Both run end to end with the fake client: no model, no network."""
import csv

import pytest

from baseline_runner import experiments as ex
from baseline_runner.__main__ import parse
from baseline_runner.chunking import make_chunks
from baseline_runner.config import CASE
from baseline_runner.corpus import load_files
from baseline_runner.fakes import FakeClient
from rag_core.ingestion.extractors import MarkdownExtractor
from rag_core.knowledge.chunking import POLICIES, chunk_text
from rag_core.knowledge.model import DocumentFormat, KnowledgeItemId, VersionTag


def context(tmp_path):
    return ex.make_context(FakeClient(), tmp_path, sampler=lambda: {}, ps=lambda: "", log=lambda *_: None)


def test_sections80_chunks_every_file_and_keeps_to_80_words():
    files = load_files()
    chunks = make_chunks(files, "sections80")
    assert {c.stem for c in chunks} == {f.stem for f in files}
    assert all(0 < len(c.text.split()) <= 80 for c in chunks)
    for f in files:
        ids = [c.chunk_id for c in chunks if c.stem == f.stem]
        assert ids == [f"{f.stem}#{n}" for n in range(1, len(ids) + 1)]


def test_sections80_in_e3_gives_the_same_chunks_as_the_core_ingestion():
    # E3 must measure the policy the core really uses, so both paths cut the Markdown the same way.
    for f in load_files():
        path = next((CASE / "documents").rglob(f"{f.stem}.md"))
        doc = MarkdownExtractor().extract(path, DocumentFormat.MARKDOWN)
        core = chunk_text(doc.text, doc.sections, POLICIES["sections80"], item_id=KnowledgeItemId(f.doc_id),
                          version_tag=VersionTag(f.version), node_id=f.node_id, source_file=f"{f.stem}.md")
        assert [c.text for c in make_chunks([f], "sections80")] == [c.text for c in core], f.stem


@pytest.mark.parametrize("policy", ["words80", "sections80"])
def test_e3_runs_with_both_chunking_policies(tmp_path, policy):
    ex.run_e3(context(tmp_path), ["qwen3-4b"], "nomic-embed-text", chunk_name=policy)
    with (tmp_path / "e3_rows.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 26 and {r["chunks"] for r in rows} == {policy}


def test_the_command_line_accepts_both_policies_and_refuses_others():
    assert parse(["e3", "--chunks", "sections80"]).chunks == "sections80"
    assert parse(["e3"]).chunks == "words80"
    with pytest.raises(SystemExit):
        parse(["e3", "--chunks", "sentences"])
