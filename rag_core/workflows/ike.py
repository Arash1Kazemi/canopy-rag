"""The IKE workflows (Phase 9, proposal section 13): add a typed relation, load the case-study seed, list a node's
relations and build its relation summary (13.3).

Like the issue workflows, a change never raises for a broken rule: the result says what went wrong and nothing is
saved. The service gets its repository, node directory and clock as arguments, and optional lookups (id -> node id or
None) for issues, knowledge items and executors, so the rules can check that a side exists and is in the right node.

This file also reads the seed CSV files of the case study (application layer; the domain reads no file).
"""
import csv
from dataclasses import dataclass
from pathlib import Path

from ..ike.model import EntityRef, IkeRelation
from ..ike.rules import check_relations
from ..ike.seed import names_from_rows, node_lookup, relations_from_rows
from ..ike.summary import summarize_node
from ..shared.kernel import DomainError

CASE_STUDY = Path(__file__).resolve().parents[2] / "case_study"
SEED_FILE = CASE_STUDY / "ike_seed_relations.csv"
SEED_SOURCE = "case_study/ike_seed_relations.csv"

RELATION_ADDED, SEEDED, FAILED = "relation added", "seeded", "failed"


@dataclass(frozen=True)
class IkeResult:
    outcome: str
    detail: str = ""
    added: int = 0
    skipped: int = 0

    @property
    def ok(self):
        return self.outcome != FAILED


class IkeService:
    def __init__(self, repository, nodes, clock, *, issue_node=None, item_node=None, executor_node=None):
        """`repository` is an IkeRepository, `nodes` a NodeDirectory, `clock()` gives the time as ISO text. The lookups
        are optional: issue_node("I01") -> "N6" or None, and the same for item_node and executor_node."""
        self.repo = repository
        self.nodes = nodes
        self.clock = clock
        self.lookups = dict(issue_node=issue_node, item_node=item_node, executor_node=executor_node)

    def add_relation(self, relation_type, source_kind, source_id, target_kind, target_id, node_id, *, evidence="",
                     basis=""):
        """Record one typed relation in a node."""
        def change():
            relation = IkeRelation(relation_type=relation_type, source=EntityRef(source_kind, source_id),
                                   target=EntityRef(target_kind, target_id), node_id=node_id,
                                   created_at=self.clock(), evidence=evidence, basis=basis)
            check_relations([relation], self.repo.all_relations(), self.nodes, **self.lookups)
            self.repo.add_all([relation])
            return IkeResult(RELATION_ADDED, f"{relation.source} {relation.relation_type.value} {relation.target} "
                                             f"in {relation.node_id}", added=1)
        return _attempt(change)

    def seed(self, rows):
        """Add the seed relations that are not stored yet, all in one transaction. A second run adds nothing."""
        def change():
            relations = relations_from_rows(rows, self.clock())
            new = [r for r in relations if not self.repo.contains(r)]
            if new:
                check_relations(new, self.repo.all_relations(), self.nodes, **self.lookups)
                self.repo.add_all(new)
            return IkeResult(SEEDED, f"{len(new)} relation(s) added, {len(relations) - len(new)} already stored",
                             added=len(new), skipped=len(relations) - len(new))
        return _attempt(change)

    def relations_of_node(self, node_id):
        node = self.nodes.require(node_id)
        return self.repo.relations_of_node(node.node_id)

    def summary(self, node_id, names=None):
        """The relation summary of one node (13.3). Raises UnknownNodeError for an unknown node."""
        node = self.nodes.require(node_id)
        return summarize_node(node.node_id, self.repo.relations_of_node(node.node_id), names=names,
                              node_name=node.name)


def _attempt(change):
    try:
        return change()
    except (DomainError, ValueError) as error:
        return IkeResult(FAILED, str(error))


# --- the case study ----------------------------------------------------------------------------------------------
def read_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@dataclass(frozen=True)
class CaseStudyIke:
    """What the IKE workflows need from the case study: the seed rows, readable names and the three lookups."""
    seed_rows: list
    names: dict
    lookups: dict


def load_case_study(folder=CASE_STUDY):
    folder = Path(folder)
    issues, people = read_rows(folder / "issues.csv"), read_rows(folder / "people.csv")
    documents = read_rows(folder / "documents_manifest.csv")
    return CaseStudyIke(
        seed_rows=read_rows(folder / "ike_seed_relations.csv"),
        names=names_from_rows(issue_rows=issues, people_rows=people, document_rows=documents),
        lookups=dict(issue_node=node_lookup(issues, "issue_id"), item_node=node_lookup(documents, "doc_id"),
                     executor_node=node_lookup(people, "person_id")))
