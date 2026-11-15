"""Test area: Registry and layers, Phase 6: the TransferRule, the layer registry file, and the SQLite hierarchy."""
import csv
import sqlite3

import pytest

from core_builders import layered_hierarchy, node, rule
from rag_core.infrastructure.registry_csv import (LAYER_COLUMNS, CsvHierarchyRepository, row_of_layer, rule_from_row)
from rag_core.infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from rag_core.organization.model import Hierarchy, Layer, LayerIndex
from rag_core.shared.kernel import DomainError, TransferDetailLevel, TransferRule

NODES, LAYERS = "registry/node_layer_registry.csv", "registry/layer_registry.csv"


# --- the TransferRule

def test_a_rule_needs_only_a_detail_level():
    r = TransferRule(TransferDetailLevel.EXECUTIVE)
    assert r.min_judge_score is None and r.max_words is None and r.required_topics == () and r.citation_level is None


@pytest.mark.parametrize("fields, message", [
    ({"detail_level": "executive"}, "needs a detail level"),
    ({"min_judge_score": 0}, "1 to 20"),
    ({"min_judge_score": 21}, "1 to 20"),
    ({"max_words": 0}, "max_words"),
    ({"citation_level": "medium"}, "citation_level"),
    ({"required_topics": ["risks"]}, "tuple of non-empty texts"),
    ({"required_topics": ("risks", " ")}, "tuple of non-empty texts"),
    ({"required_fields": ("status", "status")}, "twice"),
    ({"required_topics": ("risks",), "excluded_topics": ("risks",)}, "both required and excluded"),
])
def test_a_rule_with_a_bad_value_is_refused(fields, message):
    values = {"detail_level": TransferDetailLevel.EXECUTIVE, **fields}
    with pytest.raises(DomainError, match=message):
        TransferRule(**values)


# --- the layer registry file

def test_the_city_layer_registry_gives_every_layer_a_name_and_the_rules_of_the_proposal():
    h = CsvHierarchyRepository(NODES, LAYERS).load()
    layers = h.layers()
    assert [l.name for l in layers] == ["Strategic layer", "Parent organizations", "Subsidiaries and specialist units",
                                         "Projects, teams and executing nodes"]
    assert [l.rule.detail_level.value if l.rule else None for l in layers] == ["executive", "managerial", "technical_summary", None]
    assert "decisions needed" in layers[1].rule.required_topics and "methods" in layers[2].rule.required_topics
    assert h.problems() == []


def test_what_the_proposal_does_not_say_is_left_empty_not_invented():
    for layer in CsvHierarchyRepository(NODES, LAYERS).load().layers():
        if layer.rule:
            assert (layer.rule.excluded_topics, layer.rule.required_fields, layer.rule.output_format,
                    layer.rule.max_words, layer.rule.citation_level) == ((), (), "", None, None)


def test_the_bus_project_sends_what_the_rule_of_the_transit_agency_layer_asks_for():
    h = CsvHierarchyRepository(NODES, LAYERS).load()
    assert h.receiving_rule("N6").detail_level == TransferDetailLevel.TECHNICAL_SUMMARY
    assert h.node("N6").reporting_format == TransferDetailLevel.TECHNICAL_SUMMARY


def test_without_the_layer_file_the_hierarchy_has_no_layer_registry():
    h = CsvHierarchyRepository(NODES).load()
    assert h.layer_definition(0) is None and h.receiving_rule("N6") is None and h.problems() == []


def test_a_node_that_disagrees_with_its_layer_rule_stops_the_load(tmp_path):
    text = open(NODES, encoding="utf-8").read().replace("N4,Transit Agency,2,N1,public transit,false,managerial",
                                                        "N4,Transit Agency,2,N1,public transit,false,executive")
    changed = tmp_path / "nodes.csv"
    changed.write_text(text, encoding="utf-8", newline="")
    with pytest.raises(DomainError, match="N4 sends executive, but the transfer rule of layer 1 asks for managerial"):
        CsvHierarchyRepository(changed, LAYERS).load()


def test_layer_rows_turn_into_rules_and_back():
    with open(LAYERS, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == LAYER_COLUMNS
    for row in rows:
        layer = Layer(LayerIndex(int(row["layer_index"])), (), row["name"], row["role"], rule_from_row(row))
        assert row_of_layer(layer) == {k: v for k, v in row.items() if k != "source"}


def test_a_layer_row_with_a_bad_value_is_refused():
    base = {c: "" for c in LAYER_COLUMNS}
    assert rule_from_row(base) is None                                          # no detail level: the layer receives nothing
    with pytest.raises(DomainError, match="detail_level must be one of"):
        rule_from_row({**base, "detail_level": "brief"})
    with pytest.raises(DomainError, match="whole number"):
        rule_from_row({**base, "detail_level": "executive", "max_words": "many"})


# --- the SQLite hierarchy

@pytest.fixture
def repo(tmp_path):
    r = SqliteHierarchyRepository(tmp_path / "hierarchy.sqlite")
    yield r
    r.close()


def test_the_city_survives_a_round_trip_through_sqlite(repo):
    city = CsvHierarchyRepository(NODES, LAYERS).load()
    assert repo.is_empty()
    repo.save(city)
    assert not repo.is_empty()
    loaded = repo.load()
    assert (loaded.nodes(), loaded.layers()) == (city.nodes(), city.layers())


def test_a_change_is_stored(repo):
    h = layered_hierarchy()
    repo.save(h)
    h = repo.load()
    h.move_node("N6", "N2")
    h.change_details("N4", name="Transit Authority")
    repo.save(h)
    again = repo.load()
    assert str(again.parent("N6").node_id) == "N2" and again.node("N4").name == "Transit Authority"
    assert again.node("N6").reporting_format == TransferDetailLevel.MANAGERIAL


def test_an_inconsistent_hierarchy_is_not_saved_and_the_old_one_stays(repo):
    repo.save(layered_hierarchy())
    bad = Hierarchy()
    bad.add_node(node("N0", 0))
    bad.add_node(node("N1", 1, "N0", reporting="managerial", score=18))
    bad.define_layer(0, "Top", rule=rule("executive"))
    with pytest.raises(DomainError, match="disagree"):
        repo.save(bad)
    assert len(repo.load().nodes()) == 6


def test_the_database_refuses_a_node_with_an_unknown_parent(repo):
    with pytest.raises(sqlite3.IntegrityError):
        repo.db.execute("INSERT INTO nodes VALUES ('N9', 'x', 1, 'N99', 'y', 0, NULL, NULL, 'internal')")


def test_a_save_that_fails_halfway_leaves_the_old_hierarchy(repo, monkeypatch):
    repo.save(layered_hierarchy())
    changed = layered_hierarchy()
    changed.change_details("N4", name="New name")
    real, calls = repo._insert, []

    def failing(*args):
        calls.append(1)
        if len(calls) > 3:
            raise sqlite3.OperationalError("disk full")
        return real(*args)

    monkeypatch.setattr(repo, "_insert", failing)
    with pytest.raises(sqlite3.OperationalError):
        repo.save(changed)
    monkeypatch.undo()
    assert len(repo.load().nodes()) == 6 and repo.load().node("N4").name == "Node N4"
