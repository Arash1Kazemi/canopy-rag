"""Test area: Versioning (H03, H04), and the knowledge value objects."""
import pytest

from core_builders import version
from rag_core.knowledge.model import ContentHash, KnowledgeItem, KnowledgeItemId, VersionTag
from rag_core.shared.kernel import DomainError


def test_the_first_version_is_active_H03():
    item = KnowledgeItem.register("D90", "N1", version("1"))
    assert str(item.active_tag) == "1"


def test_a_newer_version_becomes_active_and_the_old_one_stays_H04():
    item = KnowledgeItem.register("D90", "N1", version("1", "The fleet has 120 buses."))
    item.add_version(version("2", "The fleet has 135 buses."))
    assert [str(v.tag) for v in item.versions] == ["1", "2"]
    assert str(item.active_tag) == "2"


def test_exactly_one_version_is_active_after_any_change_H03():
    item = KnowledgeItem.register("D90", "N1", version("2", "new text"))
    item.add_version(version("1", "old text"), activate=False)
    assert str(item.active_tag) == "2" and item.active_version.text == "new text"


def test_an_existing_version_tag_is_never_overwritten_H04():
    item = KnowledgeItem.register("D90", "N1", version("1"))
    with pytest.raises(DomainError, match="H04"):
        item.add_version(version("1", "different text"))


def test_an_item_has_no_way_to_delete_a_version_H04():
    item = KnowledgeItem.register("D90", "N1", version("1"))
    assert not any(hasattr(item, name) for name in ("remove_version", "delete_version", "drop_version"))
    assert isinstance(item.versions, tuple)   # a copy: changing it cannot change the item


def test_versions_get_a_sequence_and_a_link_to_the_previous_one():
    item = KnowledgeItem.register("D90", "N1", version("1", "a"))
    second = item.add_version(version("2", "b"))
    assert (second.sequence, str(second.previous_tag)) == (2, "1")


def test_a_version_from_another_node_is_rejected():
    item = KnowledgeItem.register("D90", "N1", version("1"))
    with pytest.raises(DomainError, match="belongs to node N1"):
        item.add_version(version("2", "x", node_id="N2"))


def test_an_item_without_a_valid_active_tag_cannot_be_built_H03():
    with pytest.raises(DomainError, match="H03"):
        KnowledgeItem("D90", "N1", [version("1")], active_tag=VersionTag("7"))


def test_activating_a_missing_version_is_rejected():
    item = KnowledgeItem.register("D90", "N1", version("1"))
    with pytest.raises(DomainError, match="no version 9"):
        item.activate("9")


def test_version_tags_compare_in_natural_order():
    assert VersionTag("10").sort_key() > VersionTag("9").sort_key()
    assert VersionTag("v10").sort_key() > VersionTag("v2").sort_key()
    assert VersionTag("v2").sort_key() != VersionTag("2").sort_key()   # mixed tags compare without an error


def test_the_text_fingerprint_ignores_whitespace_but_not_words():
    assert ContentHash.of_text("135  buses\n") == ContentHash.of_text("135 buses")
    assert ContentHash.of_text("135 buses") != ContentHash.of_text("120 buses")


def test_an_exact_repeat_of_a_version_is_found():
    item = KnowledgeItem.register("D90", "N1", version("1", "Shift rules: 9 hours."))
    assert item.version_with_text(ContentHash.of_text("Shift rules:  9 hours.")) is not None


def test_events_record_new_versions_and_activation():
    item = KnowledgeItem.register("D90", "N1", version("1", "a"))
    item.add_version(version("2", "b"))
    assert [e.name for e in item.events] == ["KnowledgeVersionAdded", "ActiveVersionChanged"] * 2


def test_an_item_id_with_a_slash_is_rejected():
    with pytest.raises(DomainError):
        KnowledgeItemId("D1/2")


def test_the_scope_comes_from_the_active_version():
    item = KnowledgeItem.register("D90", "N1", version("1"))
    assert (item.scope.field_of_activity, item.scope.confidentiality.value, item.scope.usage) == ("transport", "internal", "own_node")
