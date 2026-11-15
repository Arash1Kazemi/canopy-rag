"""Test area: Duplicates and overlaps (exact, near, overlap), the change summary at ingestion, and the find-duplicates command."""
import csv

import pytest

from core_builders import small_hierarchy, version
from rag_core.__main__ import main
from rag_core.fakes import FixedClock
from rag_core.infrastructure import csv_export
from rag_core.infrastructure.memory import InMemoryKnowledgeRepository
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository
from rag_core.infrastructure.sqlite import SqliteKnowledgeRepository
from rag_core.ingestion.case_study import manifest_requests
from rag_core.ingestion.extractors import Extractors
from rag_core.ingestion.service import NEW_ITEM, NEW_VERSION, IngestionService, RegistrationRequest
from rag_core.knowledge.duplicates import (DuplicateDetector, DuplicateKind, DuplicatePolicy, containment, resemblance,
                                           word_groups, words_of)
from rag_core.knowledge.model import KnowledgeItem
from rag_core.shared.kernel import DomainError


def words(prefix, start, count):
    return " ".join(f"{prefix}{i}" for i in range(start, start + count))


def item(item_id, text, node="N1", tag="1"):
    return KnowledgeItem.register(item_id, node, version(tag, text, item=item_id, node_id=node))


# --- the measures

def test_words_are_lower_case_and_punctuation_is_ignored():
    assert words_of("The FLEET, has 8.1 years | --- |") == ["the", "fleet", "has", "8", "1", "years"]


def test_word_groups_are_words_in_a_row_and_a_short_text_is_one_group():
    assert word_groups("a b c d", 3) == {("a", "b", "c"), ("b", "c", "d")}
    assert word_groups("a b", 5) == {("a", "b")}
    assert word_groups("   ", 5) == frozenset()


def test_resemblance_and_containment_in_numbers():
    a, b = {1, 2, 3, 4}, {3, 4, 5}
    assert resemblance(a, b) == pytest.approx(2 / 5)       # shared over everything in either
    assert containment(a, b) == pytest.approx(2 / 3)       # shared over the smaller one
    assert resemblance(set(), set()) == 0.0 and containment(set(), {1}) == 0.0


def test_a_policy_with_nonsense_numbers_is_refused():
    for bad in ({"word_group_size": 0}, {"near_limit": 0}, {"near_limit": 1.5}, {"min_shared_groups": 0}):
        with pytest.raises(DomainError):
            DuplicatePolicy(**bad)


def test_near_is_checked_before_overlap():
    policy = DuplicatePolicy()
    assert policy.kind_for(0.9, 500) == DuplicateKind.NEAR
    assert policy.kind_for(0.3, 20) == DuplicateKind.OVERLAP and policy.kind_for(0.3, 19) is None


# --- the detector

def test_the_same_text_in_two_items_is_an_exact_duplicate():
    found = DuplicateDetector().scan([item("D90", words("w", 0, 50)), item("D91", words("w", 0, 50))])
    assert [(r.kind, r.left_item, r.right_item, r.score) for r in found] == [(DuplicateKind.EXACT, "D90", "D91", 1.0)]


def test_a_copy_that_differs_only_in_capitals_punctuation_and_layout_is_near_with_score_1():
    a = item("D90", "The fleet has 135 buses and 12 routes, and the average age is 8.1 years.")
    b = item("D91", "# THE FLEET HAS 135 BUSES\n\nand 12 routes -- and the average age is 8.1 years.")
    (found,) = DuplicateDetector().scan([a, b])
    assert found.kind == DuplicateKind.NEAR and found.score == 1.0


def test_a_copy_with_one_word_changed_is_near():
    base = words("w", 0, 200)
    (found,) = DuplicateDetector().scan([item("D90", base), item("D91", base.replace("w50", "zz"))])
    assert found.kind == DuplicateKind.NEAR and found.score == pytest.approx(191 / 201, abs=1e-5)


def test_a_passage_copied_into_a_longer_document_is_an_overlap():
    passage = words("w", 0, 40)
    host = words("x", 0, 100) + " " + passage + " " + words("x", 100, 100)
    (found,) = DuplicateDetector().scan([item("D90", passage), item("D91", host)])
    assert (found.kind, found.shared_groups, found.score) == (DuplicateKind.OVERLAP, 36, 1.0)


def test_a_short_shared_phrase_is_not_an_overlap():
    shared = words("w", 0, 14)       # 10 shared groups, below the 20 the policy asks for
    found = DuplicateDetector().scan([item("D90", words("a", 0, 60) + " " + shared), item("D91", shared + " " + words("b", 0, 60))])
    assert found == []


def test_unrelated_texts_give_no_finding():
    assert DuplicateDetector().scan([item("D90", words("a", 0, 100)), item("D91", words("b", 0, 100))]) == []


def test_versions_of_one_item_are_never_duplicates_of_each_other():
    one = item("D92", words("w", 0, 100))
    one.add_version(version("2", words("w", 0, 100) + " extra", item="D92"))
    assert DuplicateDetector().scan([one], all_versions=True) == []


def test_by_default_only_active_versions_are_compared():
    old_text = words("w", 0, 60)
    d90 = item("D90", old_text)
    d90.add_version(version("2", words("n", 0, 60), item="D90"))
    d91 = item("D91", old_text)
    assert DuplicateDetector().scan([d90, d91]) == []
    (found,) = DuplicateDetector().scan([d90, d91], all_versions=True)
    assert (found.kind, found.left_item, found.left_tag, found.right_item) == (DuplicateKind.EXACT, "D90", "1", "D91")


def test_a_finding_lists_the_same_pair_once_in_a_fixed_order():
    found = DuplicateDetector().scan([item("D91", words("w", 0, 50)), item("D90", words("w", 0, 50))])
    assert len(found) == 1 and (found[0].left_item, found[0].right_item) == ("D90", "D91")


def test_a_finding_says_where_the_metadata_differs():
    a, b = item("D90", words("w", 0, 50), node="N1"), item("D91", words("w", 0, 50), node="N3")
    (found,) = DuplicateDetector().scan([a, b])
    assert found.same_node is False and found.metadata_differences == ("node_id",)
    assert "different nodes" in found.evidence and "differs in node_id" in found.evidence


def test_check_new_compares_one_version_with_the_others_but_not_with_its_own_item():
    other = item("D91", words("w", 0, 50))
    new = version("1", words("w", 0, 50), item="D90")
    assert [r.kind for r in DuplicateDetector().check_new("D90", new, [other])] == [DuplicateKind.EXACT]
    assert DuplicateDetector().check_new("D91", new, [other]) == []


# --- the case study

@pytest.fixture(scope="module")
def city():
    repo = InMemoryKnowledgeRepository()
    hierarchy = CsvHierarchyRepository("registry/node_layer_registry.csv").load()
    service = IngestionService(hierarchy, repo, Extractors(), clock=FixedClock(), detector=DuplicateDetector())
    return repo, [service.register(r) for r in manifest_requests("case_study")]


def test_the_city_has_no_false_duplicate_alarms_M11(city):
    repo, _ = city
    assert DuplicateDetector().scan(repo.all_items()) == []
    assert DuplicateDetector().scan(repo.all_items(), all_versions=True) == []   # D10 v1 and v2 are versions, not duplicates


def test_ingesting_the_city_with_the_detector_adds_no_duplicate_warnings(city):
    assert not [w for r in city[1] for w in r.warnings if "duplicate" in w or "overlaps" in w]


def test_the_new_bus_inventory_version_has_a_change_summary_that_names_the_numbers(city):
    d10 = city[0].get("D10")
    assert d10.versions[0].diff_summary == ""
    assert "120" in d10.versions[1].diff_summary and "135" in d10.versions[1].diff_summary


# --- ingestion with the detector

def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def make_service():
    return IngestionService(small_hierarchy(), InMemoryKnowledgeRepository(), Extractors(), clock=FixedClock(),
                            detector=DuplicateDetector())


def test_ingestion_notes_a_near_duplicate_and_still_registers_it(tmp_path):
    s = make_service()
    base = words("w", 0, 200)
    s.register(RegistrationRequest(write(tmp_path, "a.md", base), "D90", "N1", "1", "A"))
    result = s.register(RegistrationRequest(write(tmp_path, "b.md", base.replace("w50", "zz")), "D91", "N1", "1", "B"))
    assert result.outcome == NEW_ITEM
    assert any(w.startswith("near duplicate of D90 version 1") for w in result.warnings)


def test_ingestion_notes_an_overlap(tmp_path):
    s = make_service()
    passage = words("w", 0, 40)
    s.register(RegistrationRequest(write(tmp_path, "a.md", passage), "D90", "N1", "1", "A"))
    host = words("x", 0, 100) + " " + passage + " " + words("x", 100, 100)
    result = s.register(RegistrationRequest(write(tmp_path, "b.md", host), "D91", "N1", "1", "B"))
    assert any(w.startswith("overlaps with D90 version 1") for w in result.warnings)


def test_a_new_version_gets_a_change_summary_and_the_first_version_gets_none(tmp_path):
    s = make_service()
    s.register(RegistrationRequest(write(tmp_path, "a.md", "The fleet has 120 buses."), "D90", "N1", "1", "A"))
    result = s.register(RegistrationRequest(write(tmp_path, "b.md", "The fleet has 135 buses."), "D90", "N1", "2", "A"))
    assert result.outcome == NEW_VERSION
    versions = s.repo.get("D90").versions
    assert versions[0].diff_summary == "" and "'120' -> '135'" in versions[1].diff_summary


# --- storage and files

def test_the_change_summary_survives_the_database_and_reaches_the_catalog(tmp_path):
    import dataclasses
    a = item("D90", "The fleet has 120 buses.")
    a.add_version(dataclasses.replace(version("2", "The fleet has 135 buses.", item="D90"), diff_summary="1 words added, 1 removed"))
    repo = SqliteKnowledgeRepository(tmp_path / "k.sqlite")
    repo.save(a)
    assert repo.get("D90").versions[1].diff_summary == "1 words added, 1 removed"
    csv_export.export(repo, tmp_path)
    rows = list(csv.DictReader((tmp_path / "catalog.csv").open(encoding="utf-8")))
    assert [r["diff_summary"] for r in rows] == ["", "1 words added, 1 removed"]
    repo.close()


def test_find_duplicates_writes_a_csv_and_reports_missing_databases(tmp_path, capsys):
    repo = SqliteKnowledgeRepository(tmp_path / "k.sqlite")
    base = words("w", 0, 200)
    repo.save(item("D90", base))
    repo.save(item("D91", base.replace("w50", "zz")))
    repo.close()
    assert main(["find-duplicates", "--db", str(tmp_path / "k.sqlite")]) == 0
    out = capsys.readouterr().out
    assert "near" in out and "1 finding(s) among active versions" in out
    rows = list(csv.DictReader((tmp_path / "duplicates.csv").open(encoding="utf-8")))
    assert list(rows[0]) == csv_export.DUPLICATE_COLUMNS and rows[0]["kind"] == "near" and rows[0]["same_node"] == "yes"
    assert main(["find-duplicates", "--db", str(tmp_path / "missing.sqlite")]) == 2
