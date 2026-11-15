"""Test area: the chunk life cycle (created, embedded, checked, indexed) and what retrieval may use."""
import pytest

from core_builders import version
from rag_core.knowledge.lifecycle import ChunkLifecycle, ChunkStage, next_stage
from rag_core.knowledge.model import KnowledgeItem
from rag_core.shared.kernel import DomainError


def two_version_item():
    item = KnowledgeItem.register("D90", "N1", version("1", "The fleet has 120 buses."))
    item.add_version(version("2", "The fleet has 135 buses."))
    return item


def index_everything(lifecycle, item):
    for v in item.versions:
        for c in v.chunks:
            for stage in ("embedded", "checked", "indexed"):
                lifecycle.advance(c.chunk_id, stage)


def test_the_stages_follow_one_order_and_the_last_has_no_next():
    assert [s.value for s in (ChunkStage.CREATED, next_stage("created"), next_stage("embedded"), next_stage("checked"))] == \
        ["created", "embedded", "checked", "indexed"]
    assert next_stage("indexed") is None


def test_tracked_chunks_start_as_created():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    assert {life.stage(c.chunk_id) for v in item.versions for c in v.chunks} == {ChunkStage.CREATED}


def test_a_chunk_cannot_skip_a_stage_or_go_back():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    cid = item.active_version.chunks[0].chunk_id
    with pytest.raises(DomainError, match="next stage is embedded"):
        life.advance(cid, "indexed")
    life.advance(cid, "embedded")
    with pytest.raises(DomainError, match="next stage is checked"):
        life.advance(cid, "embedded")


def test_the_last_stage_has_no_next_step():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    index_everything(life, item)
    with pytest.raises(DomainError, match="none"):
        life.advance(item.active_version.chunks[0].chunk_id, "indexed")


def test_reset_sends_a_chunk_back_to_created_for_a_new_embedding():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    index_everything(life, item)
    cid = item.active_version.chunks[0].chunk_id
    life.reset(cid)
    assert life.stage(cid) == ChunkStage.CREATED


def test_an_untracked_chunk_is_an_error_not_a_default():
    with pytest.raises(DomainError, match="not tracked"):
        ChunkLifecycle().stage("D90@1#1")


def test_tracking_again_keeps_the_stage_a_chunk_already_reached():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    cid = item.active_version.chunks[0].chunk_id
    life.advance(cid, "embedded")
    life.track_item(item)
    assert life.stage(cid) == ChunkStage.EMBEDDED


def test_only_indexed_chunks_of_the_active_version_are_retrievable():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    assert life.retrievable_chunks(item) == ()            # nothing is indexed yet
    index_everything(life, item)
    assert life.retrievable_chunks(item) == item.active_version.chunks


def test_a_chunk_that_is_not_indexed_yet_is_not_retrievable():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    life.advance(item.active_version.chunks[0].chunk_id, "embedded")
    assert life.retrievable_chunks(item) == ()


def test_switching_the_active_version_changes_what_is_retrievable_and_back_needs_no_repair():
    item, life = two_version_item(), ChunkLifecycle()
    life.track_item(item)
    index_everything(life, item)
    v1, v2 = item.version("1"), item.version("2")
    assert life.retrievable_chunks(item) == v2.chunks
    item.activate("1")
    assert life.retrievable_chunks(item) == v1.chunks
    item.activate("2")
    assert life.retrievable_chunks(item) == v2.chunks
