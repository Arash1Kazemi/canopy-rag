"""Executor data from files: the seed people of the case study, the documents they wrote, and the match weights.

The seed import keeps every person id (P01 to P06) as it is. Each person becomes an Executor of kind person in the node
named in people.csv; the node is checked through the node directory. The expertise column is a list separated by
semicolons.

Documents written: the case study records authors in the first lines of some documents ("Author: ...", "Project lead:
..." or "Prepared by: ..."). A person wrote a document when that line holds the person's full name. "Signed:" lines and
attendee lists are not authorship, so they are not read. A person who is named in no such line has no documents. In the
case study this finds D15, D17 and D20, all by P01. Past projects are not recorded anywhere in the data, so they stay
empty.
"""
import re
from pathlib import Path

from ..executors.matching import MatchWeights
from ..executors.model import Executor, WrittenDocument
from .issues_csv import read_rows

PROJECT = Path(__file__).resolve().parents[2]
PEOPLE_FILE = PROJECT / "case_study" / "people.csv"
MANIFEST_FILE = PROJECT / "case_study" / "documents_manifest.csv"
DOCUMENTS_ROOT = PROJECT / "case_study" / "documents"
WEIGHTS_FILE = PROJECT / "config" / "executor_match_weights.csv"
PEOPLE_COLUMNS = ["person_id", "name", "node_id", "role", "expertise"]
WEIGHT_COLUMNS = ["factor", "weight", "meaning", "decision"]
AUTHOR_LINE = re.compile(r"^(author|project lead|prepared by)\s*:\s*(.+)$", re.IGNORECASE)
HEAD_LINES = 8     # the author line is always at the top of a document


def authors_by_name(manifest_rows, documents_root, names):
    """{person name: [WrittenDocument, ...]} from the Markdown files of the manifest. A document id with two files
    (an older version, a copy) counts once, with the title of the last row."""
    found = {}
    for row in manifest_rows:
        path = Path(documents_root) / row["file"]
        if not path.is_file():
            continue
        head = path.read_text(encoding="utf-8").splitlines()[:HEAD_LINES]
        for line in head:
            match = AUTHOR_LINE.match(line.strip())
            if match:
                for name in names:
                    if name.lower() in match.group(2).lower():
                        found.setdefault(name, {})[row["doc_id"]] = WrittenDocument(row["doc_id"], row["title"])
    return {name: sorted(docs.values(), key=lambda d: d.doc_id) for name, docs in found.items()}


def executors_from_rows(rows, nodes, written=None):
    """Seed rows (person_id, name, node_id, role, expertise) as Executors. `nodes` is a NodeDirectory: an unknown node
    raises UnknownNodeError. `written` is {name: [WrittenDocument]}."""
    written = written or {}
    executors = []
    for row in rows:
        node = nodes.require(row["node_id"].strip())
        name = row["name"].strip()
        executors.append(Executor(
            executor_id=row["person_id"].strip(), name=name, node_id=node.node_id, kind="person",
            role=row["role"].strip(), expertise=tuple(t for t in row["expertise"].split(";") if t.strip()),
            documents_written=tuple(written.get(name, ()))))
    return executors


def seed_executors(nodes, people_file=PEOPLE_FILE, manifest_file=MANIFEST_FILE, documents_root=DOCUMENTS_ROOT):
    rows = read_rows(people_file)
    if not rows or list(rows[0]) != PEOPLE_COLUMNS:
        raise ValueError(f"{people_file}: the columns must be {', '.join(PEOPLE_COLUMNS)}")
    written = authors_by_name(read_rows(manifest_file), documents_root, [r["name"].strip() for r in rows])
    return executors_from_rows(rows, nodes, written)


def load_match_weights(path=WEIGHTS_FILE):
    rows = read_rows(path)
    if not rows or list(rows[0]) != WEIGHT_COLUMNS:
        raise ValueError(f"{path}: the columns must be {', '.join(WEIGHT_COLUMNS)}")
    try:
        return MatchWeights.of({r["factor"].strip(): int(r["weight"]) for r in rows})
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from None
