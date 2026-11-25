"""Test area: Versioning (H04) and duplicates, Phase 5: the two planted problems of the case study, pinned before
retrieval exists. Documents are found by doc_id, never by file name, because a file may be converted to DOCX or PDF.

1. D10 has two versions (120 buses, then 135): only the newer one may be retrievable.
2. D12 is registered twice with the same text: the copy must add no chunks.
Both are checked with the in-memory and with the SQLite repository.
"""
import pytest

from rag_core.fakes import FixedClock
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.infrastructure.sqlite import SqliteKnowledgeRepository
from rag_core.ingestion.case_study import manifest_requests
from rag_core.ingestion.extractors import Extractors
from rag_core.ingestion.service import FAILED, NEW_ITEM, SKIPPED_REPEAT, IngestionService


@pytest.fixture(params=["memory", "sqlite"], scope="module")
def city(request, tmp_path_factory):
    repo = (InMemoryKnowledgeRepository() if request.param == "memory"
            else SqliteKnowledgeRepository(tmp_path_factory.mktemp("planted") / "k.sqlite"))
    hierarchy = CsvHierarchyRepository("registry/node_layer_registry.csv").load()
    service = IngestionService(hierarchy, repo, Extractors(), clock=FixedClock())
    results = [service.register(r) for r in manifest_requests("case_study")]
    yield repo, results
    if request.param == "sqlite":
        repo.close()


def results_of(results, item_id):
    return [r for r in results if r.request.item_id == item_id]


def chunk_ids(version):
    return {c.chunk_id for c in version.chunks}


def test_nothing_failed_so_the_checks_below_mean_something(city):
    assert not [r for r in city[1] if r.outcome == FAILED]


# --- planted problem 1: a new version (D10)

def test_d10_has_two_versions_and_v2_is_the_active_one(city):
    d10 = city[0].get("D10")
    assert [str(v.tag) for v in d10.versions] == ["1", "2"] and str(d10.active_tag) == "2"


def test_the_d10_v2_chunks_are_retrievable_and_the_v1_chunks_are_not(city):
    repo = city[0]
    d10 = repo.get("D10")
    v1, v2 = d10.version("1"), d10.version("2")
    assert v1.chunks and v2.chunks and chunk_ids(v1).isdisjoint(chunk_ids(v2))
    retrievable = {c.chunk_id for c in repo.active_chunks(d10.node_id)}
    assert chunk_ids(v2) <= retrievable
    assert retrievable.isdisjoint(chunk_ids(v1))
    assert not any(c.location.version_tag == v1.tag and c.location.item_id.value == "D10" for c in repo.active_chunks())


def test_the_old_d10_version_is_kept_unchanged_not_deleted_H04(city):
    d10 = city[0].get("D10")
    assert "120" in d10.version("1").text and "135" in d10.version("2").text
    assert "135" not in d10.version("1").text


# --- planted problem 2: an exact duplicate (D12 and its copy)

def test_d12_is_registered_twice_and_the_second_is_skipped_as_a_repeat(city):
    d12 = results_of(city[1], "D12")
    assert [r.outcome for r in d12] == [NEW_ITEM, SKIPPED_REPEAT]


def test_the_d12_copy_produces_no_chunks(city):
    repo, results = city
    first, copy = results_of(results, "D12")
    assert first.chunks > 0 and copy.chunks == 0
    d12 = repo.get("D12")
    assert len(d12.versions) == 1 and len(d12.version(d12.active_tag).chunks) == first.chunks


def test_every_d12_chunk_comes_from_the_one_stored_version(city):
    repo = city[0]
    d12_chunks = [c for c in repo.active_chunks() if c.location.item_id.value == "D12"]
    assert len(d12_chunks) == len({c.chunk_id for c in d12_chunks}) == len(repo.get("D12").active_version.chunks)


def test_the_planted_problems_leave_20_items(city):
    assert len(city[0].all_items()) == 20
