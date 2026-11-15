"""Test area: Versioning at the storage level (H04), and the repositories with the same tests for both adapters."""
import sqlite3

import pytest

from core_builders import version
from rag_core.infrastructure import csv_export
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository
from rag_core.infrastructure.sqlite import SqliteKnowledgeRepository
from rag_core.knowledge.model import ContentHash, KnowledgeItem


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    r = InMemoryKnowledgeRepository() if request.param == "memory" else SqliteKnowledgeRepository(tmp_path / "k.sqlite")
    yield r
    if request.param == "sqlite":
        r.close()


def two_items():
    a = KnowledgeItem.register("D90", "N1", version("1", "old fleet text", item="D90"))
    a.add_version(version("2", "new fleet text " * 30, item="D90"))
    b = KnowledgeItem.register("D91", "N2", version("1", "water text", item="D91", node_id="N2"))
    return a, b


def test_an_item_comes_back_as_it_was_saved(repo):
    a, _ = two_items()
    repo.save(a)
    back = repo.get("D90")
    assert [(str(v.tag), v.sequence, v.text, v.metadata) for v in back.versions] == [(str(v.tag), v.sequence, v.text, v.metadata) for v in a.versions]
    assert back.active_version.chunks == a.active_version.chunks


def test_active_chunks_are_filtered_by_node_and_use_the_active_version(repo):
    a, b = two_items()
    repo.save(a)
    repo.save(b)
    chunks = repo.active_chunks("N1")
    assert chunks and all(c.node_id == "N1" and str(c.location.version_tag) == "2" for c in chunks)
    assert len(repo.active_chunks()) == len(chunks) + 1


def test_a_text_fingerprint_finds_the_version(repo):
    a, _ = two_items()
    repo.save(a)
    found = repo.find_by_text(ContentHash.of_text("old fleet text"))
    assert [(str(i.item_id), str(v.tag)) for i, v in found] == [("D90", "1")]


def test_saving_an_item_with_a_version_missing_is_refused_H04(repo):
    a, _ = two_items()
    repo.save(a)
    shorter = KnowledgeItem("D90", "N1", [a.versions[0]], a.versions[0].tag)
    with pytest.raises(ValueError, match="H04"):
        repo.save(shorter)


def test_a_new_active_tag_is_stored(repo):
    a, _ = two_items()
    repo.save(a)
    a.activate("1")
    repo.save(a)
    assert str(repo.get("D90").active_tag) == "1"


def test_the_database_itself_refuses_to_change_a_version_H04(tmp_path):
    r = SqliteKnowledgeRepository(tmp_path / "k.sqlite")
    r.save(two_items()[0])
    with pytest.raises(sqlite3.IntegrityError, match="H04"):
        r.db.execute("UPDATE versions SET text = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="H04"):
        r.db.execute("DELETE FROM versions")
    r.close()


def test_csv_files_are_utf8_with_lf_and_no_bom(tmp_path):
    r = InMemoryKnowledgeRepository()
    for item in two_items():
        r.save(item)
    csv_export.export(r, tmp_path)
    data = (tmp_path / "chunks.csv").read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data
    assert (tmp_path / "catalog.csv").read_text(encoding="utf-8").splitlines()[1].startswith("D90,N1,1,1,no,")
