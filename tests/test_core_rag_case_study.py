"""Test area: ingestion -> indexing -> retrieval on the City case study, with fakes only (no model, no network).

The planted problems seen through retrieval: Q22 (N6 asks a water question whose answer is in N2) gets nothing from N2;
D10 v1 is never retrieved and v2 is; the D12 copy has no vectors. Both storage adapters are used.
"""
import csv

import pytest

from rag_core.fakes import FixedClock, HashingEmbedder
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository, InMemoryVectorIndex
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.infrastructure.sqlite import SqliteKnowledgeRepository
from rag_core.infrastructure.sqlite_vectors import SqliteVectorIndex
from rag_core.ingestion.case_study import manifest_requests
from rag_core.ingestion.extractors import Extractors
from rag_core.ingestion.service import IngestionService
from rag_core.knowledge.lifecycle import ChunkLifecycle, ChunkStage
from rag_core.organization.directory import HierarchyNodeDirectory
from rag_core.rag.indexing import index_chunks
from rag_core.rag.retrieval import Retriever


def question(question_id):
    with open("case_study/answer_key.csv", encoding="utf-8", newline="") as handle:
        return next(r for r in csv.DictReader(handle) if r["question_id"] == question_id)


@pytest.fixture(params=["memory", "sqlite"], scope="module")
def city(request, tmp_path_factory):
    if request.param == "memory":
        repo, index = InMemoryKnowledgeRepository(), InMemoryVectorIndex()
    else:
        folder = tmp_path_factory.mktemp("rag")
        repo, index = SqliteKnowledgeRepository(folder / "k.sqlite"), SqliteVectorIndex(folder / "k.sqlite")
    hierarchy = CsvHierarchyRepository("registry/node_layer_registry.csv").load()
    service = IngestionService(hierarchy, repo, Extractors(), clock=FixedClock())
    for r in manifest_requests("case_study"):
        service.register(r)
    lifecycle, embedder = ChunkLifecycle(), HashingEmbedder()
    report = index_chunks(repo, index, embedder, chunking_policy="words80", clock=FixedClock(), lifecycle=lifecycle)
    yield Retriever(index, embedder, HierarchyNodeDirectory(hierarchy), repo), repo, index, lifecycle, report
    if request.param == "sqlite":
        repo.close()
        index.close()


def test_every_active_chunk_is_indexed_and_nothing_else(city):
    _, repo, index, lifecycle, report = city
    active = {c.chunk_id for c in repo.active_chunks()}
    assert index.chunk_ids() == active and report.embedded == len(active)
    assert {lifecycle.stage(c) for c in active} == {ChunkStage.INDEXED}


def test_q22_n6_gets_nothing_from_n2(city):
    retriever, repo, _, _, _ = city
    q = question("Q22")
    assert q["asked_at_node"] == "N6"
    n2_chunks = {c.chunk_id for c in repo.active_chunks("N2")}
    assert n2_chunks                                            # the answer does exist, in N2
    hits = retriever.retrieve(q["question"], "N6", k=10)
    assert {h.node_id for h in hits} <= {"N6"}
    assert n2_chunks.isdisjoint(h.chunk_id for h in hits)
    assert not any("chlorine" in h.text.lower() for h in hits)


def test_the_same_question_asked_in_n2_does_find_the_chlorine_fact(city):
    retriever, _, _, _, _ = city
    hits = retriever.retrieve(question("Q22")["question"], "N2", k=3)
    assert any("chlorine" in h.text.lower() for h in hits)      # so the N6 result is the node boundary, not a bad search


def test_d10_v1_is_never_retrieved_and_v2_is(city):
    retriever, _, index, _, _ = city
    hits = retriever.retrieve(question("Q01")["question"], "N4", k=20)
    d10 = [h for h in hits if h.item_id == "D10"]
    assert d10 and {h.version_tag for h in d10} == {"2"}
    assert not any(r.item_id == "D10" and r.version_tag == "1" for r in index.records())


def test_the_d12_copy_has_no_vectors(city):
    _, repo, index, _, _ = city
    d12 = repo.get("D12")
    assert len(d12.versions) == 1                               # the copy added no version
    records = [r for r in index.records() if r.item_id == "D12"]
    assert {r.chunk_id for r in records} == {c.chunk_id for c in d12.active_version.chunks}
    assert not any("_copy" in c.location.source_file for c in d12.active_version.chunks)


def test_retrieval_is_deterministic(city):
    retriever, _, _, _, _ = city
    q = question("Q06")
    first = [(h.chunk_id, h.score) for h in retriever.retrieve(q["question"], q["asked_at_node"], k=5)]
    assert first == [(h.chunk_id, h.score) for h in retriever.retrieve(q["question"], q["asked_at_node"], k=5)]


def test_every_answer_key_question_retrieves_only_from_its_own_node(city):
    retriever, _, _, _, _ = city
    with open("case_study/answer_key.csv", encoding="utf-8", newline="") as handle:
        for q in csv.DictReader(handle):
            hits = retriever.retrieve(q["question"], q["asked_at_node"], k=5)
            assert {h.node_id for h in hits} <= {q["asked_at_node"]}, q["question_id"]
