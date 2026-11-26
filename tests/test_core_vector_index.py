"""Test area: the vector index (Phase 8A). The same tests run against the in-memory and the SQLite adapter.

H01 at the index level: a record the filter does not admit is never scored, so it can neither win nor crowd out the
node's own chunks.
"""
import pytest

from rag_core.infrastructure.memory import InMemoryVectorIndex
from rag_core.infrastructure.sqlite_vectors import SqliteVectorIndex
from rag_core.rag.vector_index import IndexFilter, IndexSignature, VectorRecord, cosine, rank
from rag_core.shared.kernel import DomainError


@pytest.fixture(params=["memory", "sqlite"])
def make_index(request, tmp_path):
    opened = []

    def make(similarity=cosine):
        index = (InMemoryVectorIndex(similarity) if request.param == "memory"
                 else SqliteVectorIndex(tmp_path / "v.sqlite", similarity))
        opened.append(index)
        return index

    yield make
    for index in opened:
        if hasattr(index, "close"):
            index.close()


def rec(chunk_id, vector, node="N4", item=None, tag="1", model="m1", policy="words80"):
    return VectorRecord(chunk_id, item or chunk_id.split("@")[0], tag, node, model, policy, tuple(vector), "2026-11-01T10:00:00Z")


def own(*pairs, node="N4"):
    return IndexFilter(node, frozenset(pairs))


def test_records_come_back_exactly_as_stored(make_index):
    index = make_index()
    stored = [rec("D1@1#1", [0.1, 0.2, 0.3]), rec("D2@1#1", [1 / 3, 2 / 3, 0.0], node="N2")]
    index.add(stored)
    assert index.records() == sorted(stored, key=lambda r: r.chunk_id)
    assert index.records("N2") == [stored[1]]
    assert index.chunk_ids() == {"D1@1#1", "D2@1#1"}


def test_adding_a_chunk_again_replaces_its_vector(make_index):
    index = make_index()
    index.add([rec("D1@1#1", [1, 0])])
    index.add([rec("D1@1#1", [0, 1])])
    assert [r.vector for r in index.records()] == [(0.0, 1.0)]


def test_signatures_name_the_model_and_policy_and_clear_drops_everything(make_index):
    index = make_index()
    assert index.signatures() == set()
    index.add([rec("D1@1#1", [1, 0])])
    assert index.signatures() == {IndexSignature("m1", "words80")}
    index.clear()
    assert index.records() == [] and index.signatures() == set()


def test_h01_a_foreign_record_with_the_perfect_score_is_never_returned(make_index):
    index = make_index()
    query = [1.0, 0.0]
    index.add([rec("D9@1#1", query, node="N2"),          # identical to the query: the best score there is
               rec("D1@1#1", [0.6, 0.8]), rec("D1@1#2", [0.0, 1.0])])
    hits = index.search(query, 10, own(("D1", "1")))
    assert [r.chunk_id for r, _ in hits] == ["D1@1#1", "D1@1#2"]
    assert all(r.node_id == "N4" for r, _ in hits)


def test_h01_the_filter_runs_before_ranking_so_k1_still_returns_the_own_chunk(make_index):
    index = make_index()
    index.add([rec("D9@1#1", [1.0, 0.0], node="N2"), rec("D1@1#1", [0.6, 0.8])])
    hits = index.search([1.0, 0.0], 1, own(("D1", "1")))
    assert [r.chunk_id for r, _ in hits] == ["D1@1#1"]   # a filter after the top 1 would have left nothing


def test_h01_a_foreign_or_inactive_record_is_never_even_scored(make_index):
    scored = []

    def spy(a, b):
        scored.append(tuple(b))
        return cosine(a, b)

    index = make_index(spy)
    index.add([rec("D9@1#1", [0.9, 0.1], node="N2"),           # another node
               rec("D1@1#1", [0.1, 0.9], tag="1"),             # an old version of D1
               rec("D1@2#1", [0.5, 0.5], tag="2")])            # the active version
    index.search([1.0, 0.0], 5, own(("D1", "2")))
    assert scored == [(0.5, 0.5)]


def test_ties_break_on_the_chunk_id_and_the_order_is_stable(make_index):
    index = make_index()
    index.add([rec("D2@1#1", [1, 0]), rec("D1@1#2", [1, 0]), rec("D1@1#1", [1, 0])])
    versions = own(("D1", "1"), ("D2", "1"))
    first = [r.chunk_id for r, _ in index.search([1, 0], 3, versions)]
    assert first == ["D1@1#1", "D1@1#2", "D2@1#1"]
    assert [r.chunk_id for r, _ in index.search([1, 0], 3, versions)] == first


def test_scores_are_cosine_and_best_first(make_index):
    index = make_index()
    index.add([rec("D1@1#1", [0.0, 1.0]), rec("D1@1#2", [1.0, 1.0])])
    hits = index.search([1.0, 0.0], 2, own(("D1", "1")))
    assert [r.chunk_id for r, _ in hits] == ["D1@1#2", "D1@1#1"]
    assert hits[0][1] == pytest.approx(2 ** -0.5) and hits[1][1] == pytest.approx(0.0)


def test_k_must_be_at_least_one(make_index):
    with pytest.raises(DomainError):
        make_index().search([1, 0], 0, own(("D1", "1")))


def test_the_sqlite_index_survives_a_restart(tmp_path):
    first = SqliteVectorIndex(tmp_path / "v.sqlite")
    first.add([rec("D1@1#1", [0.25, 0.5, 0.125])])
    first.close()
    second = SqliteVectorIndex(tmp_path / "v.sqlite")
    assert second.records() == [rec("D1@1#1", [0.25, 0.5, 0.125])]
    second.close()


def test_cosine_of_a_zero_vector_is_zero_and_lengths_must_match():
    assert cosine([0, 0], [1, 0]) == 0.0
    with pytest.raises(DomainError):
        cosine([1, 0], [1, 0, 0])


def test_rank_is_the_shared_rule_of_both_adapters():
    records = [rec("D1@1#1", [1, 0]), rec("D9@1#1", [1, 0], node="N2")]
    assert [r.chunk_id for r, _ in rank(records, [1, 0], 5, own(("D1", "1")))] == ["D1@1#1"]


def test_a_record_needs_a_vector():
    with pytest.raises(DomainError):
        rec("D1@1#1", [])
