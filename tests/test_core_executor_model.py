"""Test area: Phase 9 Executor entity and the seed import (proposal 13.1, 13.2)."""
import pytest

from executor_builders import executor, people
from issue_builders import city_nodes
from rag_core.executors.model import Executor, WrittenDocument, normalise_tag, stem
from rag_core.infrastructure.executors_csv import executors_from_rows, seed_executors
from rag_core.organization.directory import UnknownNodeError
from rag_core.shared.kernel import DomainError


def test_people_csv_imports_six_executors_with_their_own_ids():
    found = people()
    assert [str(e.executor_id) for e in found] == ["P01", "P02", "P03", "P04", "P05", "P06"]
    assert all(e.kind == "person" for e in found)
    assert {str(e.executor_id): str(e.node_id) for e in found} == {
        "P01": "N6", "P02": "N4", "P03": "N6", "P04": "N6", "P05": "N2", "P06": "N1"}


def test_expertise_tags_are_normalised_and_sorted():
    p01 = people()[0]
    assert p01.expertise == ("bus intervals", "route planning")
    assert executor(expertise=("  Bus   Fleet ", "bus fleet", "", "AIR Quality")).expertise == ("air quality", "bus fleet")


def test_documents_written_come_from_the_author_lines():
    by_id = {str(e.executor_id): e for e in people()}
    assert [d.doc_id for d in by_id["P01"].documents_written] == ["D15", "D17", "D20"]
    # attendees and signatures are not authorship
    assert all(not by_id[p].documents_written for p in ("P02", "P03", "P04", "P05", "P06"))


def test_past_projects_and_availability_are_empty_when_the_data_gives_none():
    assert all(e.past_projects == () and e.availability == "" for e in people())


def test_an_unknown_node_is_rejected_by_the_import():
    rows = [{"person_id": "P99", "name": "Nobody", "node_id": "N42", "role": "x", "expertise": "a"}]
    with pytest.raises(UnknownNodeError):
        executors_from_rows(rows, city_nodes())


def test_an_organizational_capability_is_an_executor_too():
    c = Executor(executor_id="C01", name="Workshop", node_id="N4", kind="capability", expertise=("bus maintenance",),
                 documents_written=(("D13", "Maintenance Schedule 2025"),), availability="limited")
    assert c.kind == "capability" and c.documents_written == (WrittenDocument("D13", "Maintenance Schedule 2025"),)


@pytest.mark.parametrize("bad", [
    {"executor_id": "x1"}, {"name": " "}, {"kind": "robot"}, {"availability": "busy"}, {"expertise": "one text"},
])
def test_a_broken_executor_is_refused(bad):
    fields = dict(executor_id="P90", name="A", node_id="N6", expertise=("a",))
    with pytest.raises(DomainError):
        Executor(**{**fields, **bad})


def test_the_id_never_changes():
    with pytest.raises(DomainError):
        executor().with_changes(executor_id="P91")


def test_stem_is_a_light_plural_rule():
    assert [stem(w) for w in ("routes", "buses", "bus", "surveys", "losses", "analysis", "policy", "7")] == [
        "route", "bus", "bus", "survey", "loss", "analysis", "policy", "7"]
    assert normalise_tag(" Route   Planning ") == "route planning"


def test_seed_executors_check_the_node_directory_of_the_city():
    assert len(seed_executors(city_nodes())) == 6
