"""The relation summary of one node (proposal 13.3): the IKE model as knowledge that can be sent up later.

13.3 says a higher node should be able to learn which issues a lower node is working on, which knowledge supports
each issue, which executors are connected to them, and which issues lack knowledge. RelationSummary holds exactly
that, built only from the relations of the one node (never another node's), in a fixed order, as plain values:
`to_dict()` gives strings, numbers, lists and dicts that a Phase 11 transfer package can take as it is. Which parts a
layer may receive (layer rules, confidentiality) is decided by the transfer step, not here.

The fifth point of 13.3, the nodes with an unsolved research gap, needs the research-gap rules of Phase 12.
"""
import csv
import io
from dataclasses import dataclass

from .model import RefKind, RelationType, natural_key, sorted_relations

EDGE_COLUMNS = ["relation_type", "source_kind", "source_id", "source_name", "target_kind", "target_id", "target_name",
                "evidence", "basis"]
COUNT_COLUMNS = ["relation_type", "count"]
KNOWLEDGE_LINKS = (RelationType.ISSUE_RELATED_TO_KNOWLEDGE, RelationType.ISSUE_DEPENDS_ON_KNOWLEDGE)


@dataclass(frozen=True)
class SummaryEdge:
    """One relation with readable names, ready for a table."""
    relation_type: str
    source_kind: str
    source_id: str
    source_name: str
    target_kind: str
    target_id: str
    target_name: str
    evidence: str
    basis: str

    def row(self):
        return [getattr(self, c) for c in EDGE_COLUMNS]

    def sentence(self):
        phrase = RelationType(self.relation_type).phrase
        evidence = f" [{self.evidence}]" if self.evidence else ""
        return f"{_named(self.source_id, self.source_name)} {phrase} {_named(self.target_id, self.target_name)}{evidence}"


@dataclass(frozen=True)
class RelationSummary:
    node_id: str
    node_name: str
    counts: tuple                     # ((relation type value, count), ...) for all twelve types, in 13.1 order
    edges: tuple                      # SummaryEdge, in the order of sorted_relations
    issues: tuple                     # every issue id that appears, in number order
    knowledge_by_issue: tuple         # ((issue id, (knowledge item ids, ...)), ...): related to or depends on
    executors_by_issue: tuple         # ((issue id, (executor ids, ...)), ...): can follow up
    expertise_by_executor: tuple      # ((executor id, (labels, ...)), ...)
    issues_lacking_knowledge: tuple   # ((issue id, (missing knowledge labels, ...)), ...)

    @property
    def total(self):
        return len(self.edges)

    def to_dict(self):
        """Plain values only, in a fixed order, for a transfer package."""
        return {
            "node_id": self.node_id, "node_name": self.node_name, "total": self.total,
            "counts": dict(self.counts),
            "edges": [dict(zip(EDGE_COLUMNS, e.row())) for e in self.edges],
            "issues": list(self.issues),
            "knowledge_by_issue": {k: list(v) for k, v in self.knowledge_by_issue},
            "executors_by_issue": {k: list(v) for k, v in self.executors_by_issue},
            "expertise_by_executor": {k: list(v) for k, v in self.expertise_by_executor},
            "issues_lacking_knowledge": {k: list(v) for k, v in self.issues_lacking_knowledge},
        }

    def to_text(self):
        title = f"{self.node_id} {self.node_name}".strip()
        lines = [f"IKE relation summary for {title}", f"Relations: {self.total}", "", "Counts by type:"]
        lines += [f"  {kind}: {count}" for kind, count in self.counts]
        lines += ["", "Relations:"]
        lines += [f"  {e.sentence()}" for e in self.edges] or ["  (none)"]
        lines += ["", "Issues: " + (", ".join(self.issues) or "(none)")]
        for heading, pairs in (("Knowledge per issue", self.knowledge_by_issue),
                               ("Executors who can follow up each issue", self.executors_by_issue),
                               ("Expertise per executor", self.expertise_by_executor),
                               ("Issues that lack knowledge", self.issues_lacking_knowledge)):
            lines += ["", f"{heading}:"]
            lines += [f"  {key}: {', '.join(values)}" for key, values in pairs] or ["  (none)"]
        return "\n".join(lines) + "\n"

    def edges_csv(self):
        return _csv([EDGE_COLUMNS] + [e.row() for e in self.edges])

    def counts_csv(self):
        return _csv([COUNT_COLUMNS] + [[kind, str(count)] for kind, count in self.counts])


def summarize_node(node_id, relations, *, names=None, node_name=""):
    """The summary of one node from any list of relations: relations of other nodes are left out.

    `names` maps an EntityRef to a readable name (an issue title, a document title, a person's name); a missing name
    is shown as empty and the id is used. Labels are their own name."""
    names = names or {}
    node_id = str(node_id)
    own = sorted_relations(r for r in relations if str(r.node_id) == node_id)
    counts = tuple((t.value, sum(1 for r in own if r.relation_type == t)) for t in RelationType)
    edges = tuple(SummaryEdge(r.relation_type.value, r.source.kind.value, r.source.key, _name(r.source, names),
                              r.target.kind.value, r.target.key, _name(r.target, names), r.evidence, r.basis)
                  for r in own)
    issues = sorted({side.key for r in own for side in (r.source, r.target) if side.kind == RefKind.ISSUE},
                    key=natural_key)
    return RelationSummary(
        node_id=node_id, node_name=node_name, counts=counts, edges=edges, issues=tuple(issues),
        knowledge_by_issue=_group(own, KNOWLEDGE_LINKS, by="source"),
        executors_by_issue=_group(own, (RelationType.EXECUTOR_CAN_FOLLOW_ISSUE,), by="target"),
        expertise_by_executor=_group(own, (RelationType.EXECUTOR_HAS_EXPERTISE,), by="source"),
        issues_lacking_knowledge=_group(own, (RelationType.ISSUE_LACKS_KNOWLEDGE,), by="source"))


def _group(relations, types, *, by):
    """Group the other side's keys under the `by` side's key, both in the order of the sorted relations."""
    groups = {}
    for r in relations:
        if r.relation_type in types:
            key, other = (r.source, r.target) if by == "source" else (r.target, r.source)
            values = groups.setdefault(key, [])
            if other.key not in values:
                values.append(other.key)
    return tuple((key.key, tuple(sorted(values, key=natural_key)))
                 for key, values in sorted(groups.items(), key=lambda kv: kv[0].sort_key))


def _name(side, names):
    return side.key if side.kind.is_label else names.get(side, "")


def _named(key, name):
    return f"{key} ({name})" if name and name != key else key


def _csv(rows):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerows(rows)
    return out.getvalue()
