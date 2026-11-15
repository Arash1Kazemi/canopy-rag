from baseline_runner.chunking import Chunk, make_chunks
from baseline_runner.corpus import load_files
from baseline_runner.fakes import FakeEmbedder
from baseline_runner.retrieval import Index, cosine, search


def build(chunks):
    return Index(chunks, FakeEmbedder().embed([c.text for c in chunks]))


def test_cosine_of_equal_orthogonal_and_empty_vectors():
    assert abs(cosine([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-9
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([0, 0], [1, 1]) == 0.0


def test_a_node_never_gets_a_chunk_from_another_node():
    # Hard rule H01, with the real case study and a fake embedding model.
    index = build(make_chunks(load_files(), "words80"))
    embedder = FakeEmbedder()
    for node in ("N0", "N1", "N2", "N3", "N4", "N5", "N6"):
        query = embedder.vector("chlorine residual in drinking water")
        hits = search(index, query, node, k=100)
        assert hits, node
        assert all(chunk.node_id == node for chunk, _ in hits)


def test_the_chlorine_question_finds_the_water_standard_in_its_own_node_only():
    index = build(make_chunks(load_files(), "words80"))
    query = FakeEmbedder().vector("chlorine residual in drinking water")
    assert search(index, query, "N2", k=1)[0][0].stem == "D07_water_quality_standards"
    assert all("D07" not in chunk.stem for chunk, _ in search(index, query, "N6", k=100))


def test_best_match_comes_first():
    chunks = [Chunk("a#1", "a", "D01", "N1", "buses and routes"), Chunk("b#1", "b", "D02", "N1", "water leaks")]
    hits = search(build(chunks), FakeEmbedder().vector("water leaks"), "N1", k=2)
    assert [c.stem for c, _ in hits] == ["b", "a"]


def test_equal_scores_keep_a_stable_order():
    chunks = [Chunk(f"{n}#1", n, "D01", "N1", "same words") for n in ("c", "a", "b")]
    hits = search(build(chunks), FakeEmbedder().vector("same words"), "N1", k=3)
    assert [c.stem for c, _ in hits] == ["a", "b", "c"]


def test_asking_for_more_than_exists_returns_what_exists():
    chunks = [Chunk("a#1", "a", "D01", "N1", "one"), Chunk("b#1", "b", "D02", "N2", "two")]
    assert len(search(build(chunks), FakeEmbedder().vector("one"), "N1", k=10)) == 1
