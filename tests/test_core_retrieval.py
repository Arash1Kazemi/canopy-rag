"""Test area: retrieval (Phase 8B, H01). Runs on the in-memory and on the SQLite adapters, with a fake embedder.

Pinned: a foreign-node chunk with the best score never appears (a sibling, a parent or a child are all foreign);
only active versions are searched; the metadata filter is applied before ranking; ties break on the chunk id; an
unknown node raises UnknownNodeError; an index made by another model is refused.
"""
import pytest

from core_builders import layered_hierarchy, metadata, version
from rag_core.fakes import FixedClock, HashingEmbedder
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository, InMemoryVectorIndex
from rag_core.infrastructure.sqlite import SqliteKnowledgeRepository
from rag_core.infrastructure.sqlite_vectors import SqliteVectorIndex
from rag_core.knowledge.chunking import POLICIES, chunk_text
from rag_core.knowledge.model import KnowledgeItem, KnowledgeItemId, KnowledgeVersion, VersionTag
from rag_core.organization.directory import HierarchyNodeDirectory, UnknownNodeError
from rag_core.rag.indexing import index_chunks
from rag_core.rag.retrieval import IndexOutOfDateError, RetrievalQuery, Retriever
from rag_core.shared.kernel import DomainError

CHLORINE = "The allowed chlorine residual in drinking water is 0.2 to 0.5 mg/L."
ROUTE = "Route 7 is the busiest route in the passenger survey."


def tagged(item, node, text, tag="1", **meta):
    """A version with extra metadata, such as document_type or tags."""
    chunks = chunk_text(text, (), POLICIES["words80"], item_id=KnowledgeItemId(item), version_tag=VersionTag(tag),
                        node_id=node, source_file=f"{item}_doc.md")
    return KnowledgeVersion(VersionTag(tag), text, metadata(node, text, source_file=f"{item}_doc.md", **meta), chunks)


@pytest.fixture(params=["memory", "sqlite"])
def world(request, tmp_path):
    """N4 (Transit Agency) owns D90 (two versions) and D93; N2 owns the chlorine fact; N6 (a child of N4) owns a route
    fact; N1 (the parent of N4) owns nothing."""
    if request.param == "memory":
        repo, index = InMemoryKnowledgeRepository(), InMemoryVectorIndex()
    else:
        repo, index = SqliteKnowledgeRepository(tmp_path / "k.sqlite"), SqliteVectorIndex(tmp_path / "k.sqlite")
    d90 = KnowledgeItem.register("D90", "N4", version("1", "The fleet had 120 buses in 2024.", item="D90", node_id="N4"))
    repo.save(d90)
    embedder = HashingEmbedder()
    index_chunks(repo, index, embedder, chunking_policy="words80", clock=FixedClock())   # v1 gets a vector ...
    d90 = repo.get("D90")
    d90.add_version(version("2", "The fleet has 135 buses in 2025.", item="D90", node_id="N4"))  # ... then v2 replaces it
    for item in (d90,
                 KnowledgeItem.register("D93", "N4", tagged("D93", "N4", "Drivers work shifts of at most nine hours.",
                                                            document_type="project_report", tags="shifts;drivers")),
                 KnowledgeItem.register("D92", "N2", version("1", CHLORINE, item="D92", node_id="N2")),
                 KnowledgeItem.register("D96", "N6", version("1", ROUTE, item="D96", node_id="N6"))):
        repo.save(item)
    index_chunks(repo, index, embedder, chunking_policy="words80", clock=FixedClock())
    retriever = Retriever(index, embedder, HierarchyNodeDirectory(layered_hierarchy()), repo)
    yield retriever, repo, index
    if request.param == "sqlite":
        repo.close()
        index.close()


def test_h01_a_foreign_node_chunk_with_the_best_score_never_appears(world):
    retriever, _, index = world
    assert "D92@1#1" in index.chunk_ids()                  # the foreign chunk is in the index ...
    hits = retriever.retrieve(CHLORINE, "N4", k=10)        # ... and is word for word the question
    assert hits and {h.node_id for h in hits} == {"N4"}
    assert "D92" not in {h.item_id for h in hits}


def test_h01_k1_returns_the_node_s_own_best_chunk_not_nothing(world):
    retriever, _, _ = world
    hits = retriever.retrieve(CHLORINE, "N4", k=1)
    assert len(hits) == 1 and hits[0].node_id == "N4"


def test_h01_a_parent_does_not_see_its_child_and_a_child_not_its_parent(world):
    retriever, _, _ = world
    assert "D96" not in {h.item_id for h in retriever.retrieve(ROUTE, "N4", k=10)}   # N6 is a child of N4
    assert retriever.retrieve("How many buses?", "N1", k=10) == []                    # N1 owns nothing
    assert {h.item_id for h in retriever.retrieve("How many buses?", "N6", k=10)} == {"D96"}


def test_only_the_active_version_is_searched_even_when_old_vectors_exist(world):
    retriever, _, index = world
    assert "D90@1#1" in index.chunk_ids()                  # v1 was indexed while it was active
    hits = retriever.retrieve("The fleet had 120 buses in 2024.", "N4", k=10)
    assert "D90@1#1" not in {h.chunk_id for h in hits}
    assert "D90@2#1" in {h.chunk_id for h in hits}
    assert all(h.version_tag == "2" for h in hits if h.item_id == "D90")


def test_a_hit_has_rank_score_ids_and_location(world):
    retriever, repo, _ = world
    hit = retriever.retrieve("How many buses does the fleet have?", "N4", k=1)[0]
    chunk = repo.get("D90").active_version.chunks[0]
    assert (hit.rank, hit.chunk_id, hit.item_id, hit.version_tag, hit.node_id) == (1, "D90@2#1", "D90", "2", "N4")
    assert hit.location == chunk.location and hit.text == chunk.text
    assert 0 < hit.score <= 1
    assert hit.citation().render() == "[D90_test]"


def test_hits_are_best_first_and_ties_break_on_the_chunk_id(world):
    retriever, repo, index = world
    same = "Identical text about depots."
    for item in ("D95", "D94"):
        repo.save(KnowledgeItem.register(item, "N4", version("1", same, item=item, node_id="N4")))
    index_chunks(repo, index, retriever.embedder, chunking_policy="words80", clock=FixedClock())
    hits = retriever.retrieve(same, "N4", k=4)
    assert [h.chunk_id for h in hits[:2]] == ["D94@1#1", "D95@1#1"]
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert [h.rank for h in hits] == [1, 2, 3, 4]
    assert [h.chunk_id for h in retriever.retrieve(same, "N4", k=4)] == [h.chunk_id for h in hits]


def test_the_metadata_filter_is_applied_before_ranking(world):
    retriever, _, _ = world
    # the question matches D90 best, but the filter allows only the project report D93
    hits = retriever.retrieve("The fleet has 135 buses in 2025.", "N4", k=1, metadata={"document_type": "project_report"})
    assert [h.item_id for h in hits] == ["D93"]
    assert [h.item_id for h in retriever.retrieve("buses", "N4", k=5, metadata={"tags": "drivers"})] == ["D93"]
    assert retriever.retrieve("buses", "N4", k=5, metadata={"tags": "fleet"}) == []


def test_an_unknown_metadata_field_is_refused(world):
    retriever, _, _ = world
    with pytest.raises(DomainError):
        retriever.retrieve("buses", "N4", metadata={"colour": "red"})


@pytest.mark.parametrize("node", ["N99", "", "n 4", None])
def test_an_unknown_node_raises_unknown_node_error(world, node):
    retriever, _, _ = world
    with pytest.raises(UnknownNodeError):
        retriever.retrieve("buses", node)


@pytest.mark.parametrize("text, k", [("   ", 3), ("buses", 0), ("buses", -1)])
def test_an_empty_question_or_a_bad_k_is_refused(world, text, k):
    retriever, _, _ = world
    with pytest.raises(DomainError):
        retriever.retrieve(text, "N4", k=k)


def test_an_index_made_by_another_model_is_refused(world):
    retriever, repo, index = world
    other = Retriever(index, HashingEmbedder(model_tag="another-model"), retriever.directory, repo)
    with pytest.raises(IndexOutOfDateError):
        other.retrieve("buses", "N4")


def test_the_query_is_normalized_and_embedded_once(world):
    retriever, _, _ = world
    before = len(retriever.embedder.queries)
    retriever.retrieve("  How many\n buses?  ", "N4")
    assert retriever.embedder.queries[before:] == ["How many buses?"]
