"""Test area: Versioning (metadata validation, proposal section 18.1 'knowledge metadata validation')."""
import csv

import pytest

from core_builders import metadata
from rag_core.knowledge.metadata import FIELDS
from rag_core.shared.kernel import DomainError


def test_a_complete_record_is_accepted_and_sorted():
    record = metadata()
    assert record["node_id"] == "N1" and list(record.as_dict()) == sorted(record.as_dict())


def test_a_missing_required_field_is_named():
    values = metadata().as_dict()
    del values["title"]
    with pytest.raises(DomainError, match="title"):
        type(metadata())(values)


def test_an_unknown_field_is_rejected():
    with pytest.raises(DomainError, match="unknown metadata field 'colour'"):
        metadata(colour="blue")


@pytest.mark.parametrize("name, value", [
    ("confidentiality", "secret"), ("document_type", "email"), ("file_sha256", "abc"),
    ("ingested_at", "yesterday"), ("page_count", "two"), ("tags", "a;;b"),
])
def test_a_broken_value_is_rejected(name, value):
    with pytest.raises(DomainError, match=name):
        metadata(**{name: value})


def test_an_empty_optional_field_is_dropped():
    assert "owner" not in metadata(owner="  ").as_dict()


def test_a_change_makes_a_new_record_and_keeps_the_old_one():
    old = metadata()
    new = old.with_changes(title="Another")
    assert (old["title"], new["title"]) == ("A title", "Another")


def test_the_schema_page_lists_exactly_the_fields_of_the_code():
    with open("architecture/metadata_fields.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [(r["field"], r["required"]) for r in rows] == [(f.name, "yes" if f.required else "no") for f in FIELDS]
