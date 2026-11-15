"""Test area: Answers and citations (the citation model)."""
import pytest

from core_builders import version
from rag_core.rag.citation import Citation, parse_citations
from rag_core.shared.kernel import DomainError


def test_a_citation_built_from_a_chunk_cites_the_file_stem():
    chunk = version("2", source_file="N4_transit_agency/D10_bus_fleet_inventory_v2.md", item="D10", node_id="N1").chunks[0]
    citation = Citation.of_chunk(chunk)
    assert citation.render() == "[D10_bus_fleet_inventory_v2]"
    assert citation.chunk_id == "D10@2#1"


def test_the_long_form_shows_pages_headings_and_chunk():
    c = Citation("D19_meeting_minutes_2025-06-18", "D19@1#2", 1, 1, ("Minutes", "Decisions"))
    assert c.render_long() == "[D19_meeting_minutes_2025-06-18, p. 1, Minutes > Decisions, chunk D19@1#2]"
    assert Citation("D16_passenger_survey_2025", page_start=2, page_end=3).render_long() == "[D16_passenger_survey_2025, pp. 2-3]"


def test_citations_are_parsed_in_order_once_each_and_lists_are_split():
    answer = "135 buses [D10_bus_fleet_inventory_v2]. Also [D13_maintenance_schedule_2025, D10_bus_fleet_inventory_v2]."
    assert parse_citations(answer) == ["D10_bus_fleet_inventory_v2", "D13_maintenance_schedule_2025"]


def test_text_in_brackets_that_is_not_a_stem_is_ignored():
    assert parse_citations("See [the report above] and [D20_cost_estimate]") == ["D20_cost_estimate"]


def test_a_citation_with_a_space_in_the_stem_is_rejected():
    with pytest.raises(DomainError):
        Citation("D10 bus")
