"""Test area: Ingestion (the real DOCX and PDF files of the case study). scripts/make_real_files.py made them from the
Markdown sources; the manifest names them in `real_file` and `real_format`. The Markdown stays the source of truth, and
a real file keeps the stem of its Markdown file, so citations and the answer key do not change."""
import csv
import importlib.util
import re
from pathlib import Path

import pytest

from rag_core.fakes import FixedClock, StubVisionModel
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.ingestion.case_study import REAL_FORMATS, manifest_requests
from rag_core.ingestion.extractors import Extractors
from rag_core.ingestion.service import FAILED, NEW_ITEM, NEW_VERSION, SKIPPED_REPEAT, IngestionService
from rag_core.rag.citation import Citation

HAS_PYPDF = importlib.util.find_spec("pypdf") is not None
HAS_PDFIUM = importlib.util.find_spec("pypdfium2") is not None
needs_pdf = pytest.mark.skipif(not HAS_PYPDF, reason="pypdf is not installed")
CASE = Path("case_study")
D19_STEM = "D19_meeting_minutes_2025-06-18"


def manifest():
    with (CASE / "documents_manifest.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ingest(requests, vision=None):
    service = IngestionService(CsvHierarchyRepository("registry/node_layer_registry.csv").load(),
                               InMemoryKnowledgeRepository(), Extractors(vision=vision), clock=FixedClock())
    return service.repo, [service.register(r) for r in requests]


@pytest.fixture(scope="module")
def city():
    if not HAS_PYPDF:
        pytest.skip("pypdf is not installed")
    return ingest(manifest_requests(CASE, real_files=True))


# --- the manifest
def test_the_manifest_names_two_docx_two_text_pdfs_and_one_image_only_pdf():
    real = {row["doc_id"]: row["real_format"] for row in manifest() if row["real_file"]}
    assert sorted(real.values()) == ["docx", "docx", "pdf_image_only", "pdf_text", "pdf_text"]
    assert real["D19"] == "pdf_image_only"


def test_each_real_file_exists_beside_its_markdown_with_the_same_stem():
    for row in manifest():
        if not row["real_file"]:
            assert row["real_format"] == ""
            continue
        md, real = Path(row["file"]), Path(row["real_file"])
        assert (CASE / "documents" / real).is_file(), real
        assert real.parent == md.parent and real.stem == md.stem
        assert real.suffix == REAL_FORMATS[row["real_format"]]


def test_the_version_and_duplicate_traps_stay_markdown():
    assert all(not row["real_file"] for row in manifest() if row["doc_id"] in ("D10", "D12"))


def test_the_answer_key_sources_are_still_the_file_stems():
    stems = {Path(row["file"]).stem for row in manifest()}
    with (CASE / "answer_key.csv").open(encoding="utf-8", newline="") as handle:
        for q in csv.DictReader(handle):
            for stem in re.findall(r"D\d\d_[\w.-]+", q["source_files"]):
                assert stem in stems, (q["question_id"], stem)


@needs_pdf
def test_the_d19_pdf_has_pages_but_no_text_layer():
    from pypdf import PdfReader
    pages = PdfReader(str(CASE / "documents" / "N6_bus_network_project" / f"{D19_STEM}.pdf")).pages
    assert len(pages) >= 1 and all(not (p.extract_text() or "").strip() for p in pages)


# --- which file a request reads
def test_requests_read_the_real_files_and_keep_the_markdown_for_d19_without_an_lvm():
    by_id = {(r.item_id, r.version_tag): r for r in manifest_requests(CASE, real_files=True)}
    assert by_id[("D13", "1")].source_file == "N4_transit_agency/D13_maintenance_schedule_2025.docx"
    assert by_id[("D17", "1")].path.suffix == ".pdf"
    d19 = by_id[("D19", "1")]
    assert d19.path.suffix == ".md" and any("image-only" in n and "--ocr" in n for n in d19.notes)


def test_with_an_lvm_d19_is_read_from_its_image_only_pdf():
    d19 = next(r for r in manifest_requests(CASE, real_files=True, lvm=True) if r.item_id == "D19")
    assert d19.source_file == f"N6_bus_network_project/{D19_STEM}.pdf" and not d19.notes


def test_by_default_the_markdown_is_read_and_an_old_manifest_still_works():
    assert all(r.path.suffix == ".md" and not r.notes for r in manifest_requests(CASE))
    old = [{k: v for k, v in row.items() if k not in ("real_file", "real_format")} for row in manifest()]
    assert all(r.path.suffix == ".md" for r in manifest_requests(CASE, read_rows=lambda _: old, real_files=True))


# --- the whole city, read from the real files
def test_the_city_read_from_real_files_is_still_20_items(city):
    repo, results = city
    outcomes = [r.outcome for r in results]
    assert len(repo.all_items()) == 20 and outcomes.count(NEW_ITEM) == 20 and FAILED not in outcomes
    assert outcomes.count(NEW_VERSION) == 1 and outcomes.count(SKIPPED_REPEAT) == 1
    assert str(repo.get("D10").active_tag) == "2" and len(repo.get("D12").versions) == 1


def test_the_metadata_says_how_each_real_file_was_read(city):
    repo = city[0]
    method = {i: repo.get(i).active_version.metadata["extraction_method"] for i in ("D02", "D04", "D13", "D17", "D19")}
    assert method == {"D02": "pdf_text", "D04": "docx_xml", "D13": "docx_xml", "D17": "pdf_text", "D19": "markdown"}
    d19 = next(r for r in city[1] if r.request.item_id == "D19")
    assert any("--ocr" in w for w in d19.warnings)


def test_pdf_chunks_carry_page_numbers_and_cite_the_unchanged_stem(city):
    for item_id, stem in (("D17", "D17_pilot_test_report"), ("D02", "D02_city_strategy_2030")):
        version = city[0].get(item_id).active_version
        assert version.metadata["page_count"] == "1"
        for chunk in version.chunks:
            citation = Citation.of_chunk(chunk)
            assert (chunk.location.page_start, chunk.location.page_end) == (1, 1)
            assert citation.render() == f"[{stem}]" and f"[{stem}, p. 1," in citation.render_long()


def test_docx_chunks_have_no_page_but_keep_their_heading_path(city):
    chunks = city[0].get("D13").active_version.chunks
    assert all(c.location.page_start is None for c in chunks)
    assert any(c.location.heading_path[:1] == ("Maintenance Schedule 2025",) for c in chunks)


@pytest.mark.skipif(not (HAS_PYPDF and HAS_PDFIUM), reason="pypdf and pypdfium2 are needed")
def test_the_image_only_d19_goes_to_the_lvm_and_its_citations_name_the_page():
    text = (CASE / "documents" / "N6_bus_network_project" / f"{D19_STEM}.md").read_text(encoding="utf-8")
    lvm = StubVisionModel([text])
    d19 = [r for r in manifest_requests(CASE, real_files=True, lvm=True) if r.item_id == "D19"]
    repo, results = ingest(d19, vision=lvm)
    assert results[0].outcome == NEW_ITEM, results[0].detail
    assert len(lvm.seen) == 1 and lvm.seen[0].startswith(b"\x89PNG")
    version = repo.get("D19").active_version
    assert version.metadata["extraction_method"] == "lvm_ocr" and version.metadata["file_format"] == "pdf"
    assert all(Citation.of_chunk(c).render_long().startswith(f"[{D19_STEM}, p. 1,") for c in version.chunks)
