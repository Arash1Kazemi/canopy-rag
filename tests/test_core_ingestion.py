"""Test area: Ingestion (the use case), run on the case study with an in-memory repository."""
import pytest

from core_builders import small_hierarchy
from rag_core.fakes import FixedClock
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.ingestion.case_study import manifest_requests
from rag_core.ingestion.extractors import Extractors
from rag_core.ingestion.samples import markdown_to_docx
from rag_core.ingestion.service import FAILED, NEW_ITEM, NEW_VERSION, SKIPPED_REPEAT, IngestionService, RegistrationRequest


def service(hierarchy=None, repo=None):
    return IngestionService(hierarchy or CsvHierarchyRepository("registry/node_layer_registry.csv").load(),
                            repo or InMemoryKnowledgeRepository(), Extractors(), clock=FixedClock())


@pytest.fixture(scope="module")
def city():
    s = service()
    results = [s.register(r) for r in manifest_requests("case_study")]
    return s.repo, results


def request(tmp_path, text, item="D90", node="N1", tag="1", name="D90_test.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return RegistrationRequest(path, item, node, tag, "Test")


def test_the_22_case_study_files_become_20_items(city):
    repo, results = city
    assert len(repo.all_items()) == 20
    assert [r.outcome for r in results].count(NEW_ITEM) == 20 and not [r for r in results if r.outcome == FAILED]


def test_the_newer_bus_inventory_is_active_and_the_old_one_is_kept(city):
    d10 = city[0].get("D10")
    assert [str(v.tag) for v in d10.versions] == ["1", "2"] and str(d10.active_tag) == "2"


def test_the_copy_of_the_shift_rules_is_not_indexed_twice(city):
    repo, results = city
    copy = next(r for r in results if r.request.path.name == "D12_driver_shift_rules_copy.md")
    assert copy.outcome == SKIPPED_REPEAT
    assert len(repo.get("D12").versions) == 1


def test_every_chunk_belongs_to_the_node_of_its_item(city):
    repo = city[0]
    assert all(c.node_id == item.node_id for item in repo.all_items() for v in item.versions for c in v.chunks)


def test_active_chunks_of_one_node_come_only_from_that_node_H01(city):
    chunks = city[0].active_chunks("N6")
    assert chunks and {c.location.item_id.value for c in chunks} == {"D11", "D15", "D16", "D17", "D18", "D19", "D20"}


def test_metadata_takes_field_and_confidentiality_from_the_node(city):
    meta = city[0].get("D09").active_version.metadata
    assert (meta["field_of_activity"], meta["confidentiality"], meta["ingested_at"]) == ("housing", "confidential", "2026-11-01T10:00:00Z")


def test_a_terminal_node_takes_only_one_summary_document_H10(tmp_path):
    s = service(small_hierarchy())
    assert s.register(request(tmp_path, "summary one", "D91", "N3", name="a.md")).outcome == NEW_ITEM
    second = s.register(request(tmp_path, "summary two", "D92", "N3", name="b.md"))
    assert second.outcome == FAILED and "H10" in second.detail


def test_a_terminal_node_can_get_a_new_version_of_its_summary(tmp_path):
    s = service(small_hierarchy())
    s.register(request(tmp_path, "summary one", "D91", "N3", name="a.md"))
    assert s.register(request(tmp_path, "summary two", "D91", "N3", tag="2", name="b.md")).outcome == NEW_VERSION


def test_new_text_under_an_existing_version_tag_is_refused_H04(tmp_path):
    s = service(small_hierarchy())
    s.register(request(tmp_path, "first text", name="a.md"))
    result = s.register(request(tmp_path, "changed text", name="b.md"))
    assert result.outcome == FAILED and "H04" in result.detail


def test_an_older_version_registered_late_does_not_become_active(tmp_path):
    s = service(small_hierarchy())
    s.register(request(tmp_path, "version two", tag="2", name="a.md"))
    result = s.register(request(tmp_path, "version one", tag="1", name="b.md"))
    assert result.outcome == NEW_VERSION and result.active_tag == "2"


def test_an_unknown_node_fails_without_stopping_the_batch(tmp_path):
    result = service(small_hierarchy()).register(request(tmp_path, "text", node="N99"))
    assert result.outcome == FAILED and "unknown node N99" in result.detail


def test_an_item_cannot_move_to_another_node(tmp_path):
    s = service(small_hierarchy())
    s.register(request(tmp_path, "text one", name="a.md"))
    result = s.register(request(tmp_path, "text two", node="N0", tag="2", name="b.md"))
    assert result.outcome == FAILED and "belongs to node N1" in result.detail


def test_the_same_text_in_another_item_is_noted_for_phase_5(tmp_path):
    s = service(small_hierarchy())
    s.register(request(tmp_path, "identical words", item="D90", name="a.md"))
    result = s.register(request(tmp_path, "identical words", item="D91", name="b.md"))
    assert result.outcome == NEW_ITEM and result.warnings == ("same text as D90 version 1",)


def test_a_docx_copy_of_plain_markdown_is_the_same_version(tmp_path):
    md = (tmp_path / "D90_test.md")
    md.write_text("# Fleet\n\nThe fleet has 135 buses.\n\n## Age\n\nAverage age 8.1 years.\n", encoding="utf-8")
    markdown_to_docx(md.read_text(encoding="utf-8"), tmp_path / "D90_test.docx")
    s = service(small_hierarchy())
    s.register(RegistrationRequest(md, "D90", "N1", "1", "Test"))
    result = s.register(RegistrationRequest(tmp_path / "D90_test.docx", "D90", "N1", "1", "Test"))
    assert result.outcome == SKIPPED_REPEAT   # the same normalized text, so the same version


def test_a_docx_copy_with_a_table_loses_only_the_markdown_separator_line(tmp_path):
    text = "# Fleet\n| Type | Buses |\n|---|---|\n| Diesel | 78 |\n"
    (tmp_path / "a.md").write_text(text, encoding="utf-8")
    markdown_to_docx(text, tmp_path / "a.docx")
    s = service(small_hierarchy())
    s.register(RegistrationRequest(tmp_path / "a.md", "D90", "N1", "1", "Test"))
    result = s.register(RegistrationRequest(tmp_path / "a.docx", "D90", "N1", "1", "Test"))
    # the texts differ by '|---|---|', so the same tag is refused: a converted copy goes into a fresh database
    assert result.outcome == FAILED and "H04" in result.detail


def test_converted_copies_are_used_where_they_exist_and_originals_elsewhere(tmp_path):
    markdown_to_docx("# Minutes\nRoute 7 pilot.\n", tmp_path / "N6_bus_network_project" / "D19_meeting_minutes_2025-06-18.docx")
    requests = {r.item_id + "v" + r.version_tag: r for r in manifest_requests("case_study", tmp_path, ".docx")}
    assert requests["D19v1"].path.suffix == ".docx"
    assert requests["D19v1"].source_file == "N6_bus_network_project/D19_meeting_minutes_2025-06-18.docx"
    assert requests["D20v1"].path.suffix == ".md" and requests["D20v1"].path.exists()
