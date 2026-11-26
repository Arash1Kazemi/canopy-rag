"""The case-study seed of the IKE model, and readable names for summaries. Pure functions over rows (lists of dicts);
the application layer reads the CSV files.

`derive_relations` finds the two kinds of relation that the case-study records state directly:
- issues.csv: a sub-issue's parent_issue_id gives "the parent decomposes into the sub-issue";
- people.csv: each expertise (separated by ";") gives "the person has expertise in it", in the person's node.
The seed file case_study/ike_seed_relations.csv holds these plus the relations that a document states clearly, each
with the document as evidence and a basis note. A test checks that every derived relation is in the seed file.
"""
from .model import EntityRef, IkeRelation, RefKind, RelationType

SEED_COLUMNS = ["relation_type", "source_kind", "source_id", "target_kind", "target_id", "node_id", "evidence", "basis"]


def relations_from_rows(rows, created_at):
    """IkeRelations from seed rows (SEED_COLUMNS). Raises DomainError for a row that breaks a rule of the model."""
    return [IkeRelation(relation_type=row["relation_type"], source=EntityRef(row["source_kind"], row["source_id"]),
                        target=EntityRef(row["target_kind"], row["target_id"]), node_id=row["node_id"],
                        created_at=created_at, evidence=row.get("evidence", ""), basis=row.get("basis", ""))
            for row in rows]


def rows_of_relations(relations):
    """The seed rows of relations (no date), the inverse of relations_from_rows."""
    return [{"relation_type": r.relation_type.value, "source_kind": r.source.kind.value, "source_id": r.source.key,
             "target_kind": r.target.kind.value, "target_id": r.target.key, "node_id": str(r.node_id),
             "evidence": r.evidence, "basis": r.basis} for r in relations]


def derive_relations(issue_rows, people_rows, created_at):
    """The relations the records state directly (see the module note), in file order."""
    relations = []
    for row in issue_rows:
        parent = (row.get("parent_issue_id") or "").strip()
        if parent:
            relations.append(IkeRelation(
                relation_type=RelationType.ISSUE_DECOMPOSES_INTO_ISSUE, source=EntityRef(RefKind.ISSUE, parent),
                target=EntityRef(RefKind.ISSUE, row["issue_id"]), node_id=row["node_id"], created_at=created_at,
                basis="issues.csv parent_issue_id"))
    for row in people_rows:
        for label in (row.get("expertise") or "").split(";"):
            if label.strip():
                relations.append(IkeRelation(
                    relation_type=RelationType.EXECUTOR_HAS_EXPERTISE, source=EntityRef(RefKind.EXECUTOR, row["person_id"]),
                    target=EntityRef(RefKind.EXPERTISE, label), node_id=row["node_id"], created_at=created_at,
                    basis="people.csv expertise"))
    return relations


def names_from_rows(*, issue_rows=(), people_rows=(), document_rows=()):
    """EntityRef -> readable name: an issue's title, the answer of an issue, a person's name and role, a document's
    title (the manifest has one row per file; the first title of a document id is used)."""
    names = {}
    for row in issue_rows:
        names[EntityRef(RefKind.ISSUE, row["issue_id"])] = row["title"]
        names[EntityRef(RefKind.ANSWER, row["issue_id"])] = f"answer to: {row['title']}"
    for row in people_rows:
        names[EntityRef(RefKind.EXECUTOR, row["person_id"])] = f"{row['name']}, {row['role']}"
    for row in document_rows:
        names.setdefault(EntityRef(RefKind.KNOWLEDGE_ITEM, row["doc_id"]), row["title"])
    return names


def node_lookup(rows, id_column, node_column="node_id"):
    """A lookup id -> node id (or None) from rows, for the rules: issue_node, item_node, executor_node."""
    table = {}
    for row in rows:
        table.setdefault(row[id_column], row[node_column])
    return lambda key: table.get(str(key))
