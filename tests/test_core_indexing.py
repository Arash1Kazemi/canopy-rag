"""Test area: the indexing use case (Phase 8A). Runs on the in-memory and on the SQLite adapters.

What is pinned: only active versions are embedded; chunks move to `indexed` (A12); a second run embeds nothing; a
change of embedding model or chunking policy rebuilds the index; embeddings go out in batches; a wrong model reply
stops the run.
"""
import pytest

from core_builders import version
from rag_core.fakes import FixedClock, HashingEmbedder
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository, InMemoryVectorIndex
from rag_core.infrastructure.sqlite import SqliteKnowledgeRepository
from rag_core.infrastructure.sqlite_vectors import SqliteVectorIndex
from rag_core.knowledge.chunking import POLICIES
from rag_core.knowledge.lifecycle import ChunkLifecycle, ChunkStage
from rag_core.knowledge.model import KnowledgeItem
from rag_core.rag.indexing import IndexingError, index_chunks
from rag_core.rag.vector_index import IndexSignature
from rag_core.shared.kernel import DomainError

LONG_V1 = " ".join(f"old{i}" for i in range(100)) + " the fleet had 120 buses"
LONG_V2 = " ".join(f"new{i}" for i in range(170)) + " the fleet has 135 buses"   # three words80 chunks


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryKnowledgeRepository(), InMemoryVectorIndex()
    else:
        repo, index = SqliteKnowledgeRepository(tmp_path / "k.sqlite"), SqliteVectorIndex(tmp_path / "k.sqlite")
        yield repo, index
        repo.close()
        index.close()


def fleet(repo):
    """D90 in N4 with two versions (v2 active) and D91 in N2 with one."""
    d90 = KnowledgeItem.register("D90", "N4", version("1", LONG_V1, item="D90", node_id="N4"))
    d90.add_version(version("2", LONG_V2, item="D90", node_id="N4"))
    d91 = KnowledgeItem.register("D91", "N2", version("1", "Chlorine residual is 0.2 to 0.5 mg/L.", item="D91", node_id="N2"))
    repo.save(d90)
    repo.save(d91)
    return d90, d91


def run(repo, index, embedder=None, policy="words80", **kw):
    return index_chunks(repo, index, embedder or HashingEmbedder(), chunking_policy=policy, clock=FixedClock(), **kw)


def ids(chunks):
    return {c.chunk_id for c in chunks}


def test_only_the_chunks_of_active_versions_are_embedded(store):
    repo, index = store
    d90, d91 = fleet(repo)
    report = run(repo, index)
    assert index.chunk_ids() == ids(d90.active_version.chunks) | ids(d91.active_version.chunks)
    assert index.chunk_ids().isdisjoint(ids(d90.version("1").chunks))
    assert report.embedded == report.eligible == 4 and report.kept == 0 and not report.rebuilt


def test_each_vector_carries_chunk_item_version_node_model_policy_and_time(store):
    repo, index = store
    fleet(repo)
    run(repo, index)
    record = next(r for r in index.records() if r.chunk_id == "D90@2#1")
    assert (record.item_id, record.version_tag, record.node_id) == ("D90", "2", "N4")
    assert (record.embedding_model, record.chunking_policy, record.indexed_at) == ("fake-hash-64", "words80", "2026-11-01T10:00:00Z")
    assert len(record.vector) == 64


def test_embedded_chunks_move_to_indexed_and_old_versions_stay_created(store):
    repo, index = store
    d90, _ = fleet(repo)
    lifecycle = ChunkLifecycle()
    run(repo, index, lifecycle=lifecycle)
    assert {lifecycle.stage(c) for c in ids(d90.active_version.chunks)} == {ChunkStage.INDEXED}
    assert {lifecycle.stage(c) for c in ids(d90.version("1").chunks)} == {ChunkStage.CREATED}
    assert ids(lifecycle.retrievable_chunks(d90)) == ids(d90.active_version.chunks)


def test_a_second_run_embeds_nothing(store):
    repo, index = store
    fleet(repo)
    embedder = HashingEmbedder()
    run(repo, index, embedder)
    calls = list(embedder.batches)
    again = run(repo, index, embedder)
    assert embedder.batches == calls
    assert (again.embedded, again.kept, again.batches, again.rebuilt) == (0, 4, 0, False)


def test_a_new_active_version_embeds_only_its_chunks(store):
    repo, index = store
    d90 = KnowledgeItem.register("D90", "N4", version("1", LONG_V1, item="D90", node_id="N4"))
    repo.save(d90)
    run(repo, index)
    d90 = repo.get("D90")
    d90.add_version(version("2", LONG_V2, item="D90", node_id="N4"))
    repo.save(d90)
    report = run(repo, index)
    assert report.embedded == 3 and report.kept == 0
    assert ids(d90.version("1").chunks) | ids(d90.version("2").chunks) == index.chunk_ids()  # v1 vectors stay; retrieval filters them


def test_the_stages_come_back_from_the_index_after_a_restart(store):
    repo, index = store
    d90, _ = fleet(repo)
    run(repo, index)
    fresh = ChunkLifecycle()                       # a new process: the stages were in memory only
    embedder = HashingEmbedder()
    report = run(repo, index, embedder, lifecycle=fresh)
    assert embedder.batches == [] and report.kept == 4
    assert {fresh.stage(c) for c in ids(d90.active_version.chunks)} == {ChunkStage.INDEXED}


def test_a_different_embedding_model_rebuilds_the_index(store):
    repo, index = store
    fleet(repo)
    run(repo, index)
    lifecycle = ChunkLifecycle()
    other = HashingEmbedder(dims=32, model_tag="other-model")
    report = run(repo, index, other, lifecycle=lifecycle)
    assert report.rebuilt and report.embedded == 4
    assert index.signatures() == {IndexSignature("other-model", "words80")}
    assert {len(r.vector) for r in index.records()} == {32}
    assert {lifecycle.stage(c) for c in index.chunk_ids()} == {ChunkStage.INDEXED}


def test_a_different_chunking_policy_rebuilds_the_index(store):
    repo, index = store
    fleet(repo)
    run(repo, index)
    report = run(repo, index, policy=POLICIES["sections80"])
    assert report.rebuilt and report.embedded == 4
    assert index.signatures() == {IndexSignature("fake-hash-64", "sections80")}


def test_embeddings_are_sent_in_batches(store):
    repo, index = store
    fleet(repo)
    embedder = HashingEmbedder()
    report = run(repo, index, embedder, batch_size=3)
    assert embedder.batches == [3, 1] and report.batches == 2


class BrokenEmbedder(HashingEmbedder):
    def embed(self, texts):
        return super().embed(texts)[:-1]


def test_a_missing_vector_stops_the_run(store):
    repo, index = store
    fleet(repo)
    with pytest.raises(IndexingError):
        run(repo, index, BrokenEmbedder(), batch_size=10)
    assert index.chunk_ids() == set()


def test_bad_arguments_are_refused(store):
    repo, index = store
    with pytest.raises(DomainError):
        run(repo, index, batch_size=0)
    with pytest.raises(DomainError):
        run(repo, index, policy="")
