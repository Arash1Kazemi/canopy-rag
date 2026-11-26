"""Builders for the Phase 7 issue tests: the City hierarchy, its node directory, the seed issues and the weights."""
from pathlib import Path

from rag_core.fakes import FixedClock
from rag_core.infrastructure.issues_csv import SEED_FILE, issues_from_rows, load_progress_weights, read_rows
from rag_core.infrastructure.registry_csv import hierarchy_from_rows
from rag_core.issues.model import Issue
from rag_core.organization.directory import HierarchyNodeDirectory

PROJECT = Path(__file__).resolve().parent.parent
CLOCK = FixedClock("2026-11-25T10:00:00Z")


def city_hierarchy():
    return hierarchy_from_rows(read_rows(PROJECT / "registry" / "node_layer_registry.csv"),
                               read_rows(PROJECT / "registry" / "layer_registry.csv"))


def city_nodes():
    return HierarchyNodeDirectory(city_hierarchy())


def seed_issues():
    return issues_from_rows(read_rows(SEED_FILE), CLOCK(), city_nodes())


def weights():
    return load_progress_weights()


def issue(issue_id="I90", node="N6", title="A test issue", description="Something to look at", **fields):
    fields.setdefault("created_at", CLOCK())
    fields.setdefault("field_of_activity", "transport")
    return Issue(issue_id=issue_id, node_id=node, title=title, description=description, **fields)
