"""Issue data from CSV files: the seed issues of the case study and the progress weights (config/).

The seed import keeps every id, node, parent, title and description as they are (decision A36). The old status values
are mapped to the ten statuses (decision A30; "in progress" becomes in_progress, the others keep their names). Each
issue's sibling position is its order in the file, and its field of activity is its node's.
"""
import csv
from pathlib import Path

from ..issues.model import Issue
from ..issues.progress import ProgressWeights
from ..issues.status import parse_status

PROJECT = Path(__file__).resolve().parents[2]
SEED_FILE = PROJECT / "case_study" / "issues.csv"
SEED_SOURCE = "case_study/issues.csv"
WEIGHTS_FILE = PROJECT / "config" / "issue_progress_weights.csv"
WEIGHT_COLUMNS = ["factor", "weight", "meaning", "decision"]


def read_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def issues_from_rows(rows, created_at, nodes):
    """Seed rows (issue_id, node_id, parent_issue_id, title, description, status) as Issues. `nodes` is a NodeDirectory."""
    issues, positions = [], {}
    for row in rows:
        node = nodes.require(row["node_id"].strip())
        parent = (row.get("parent_issue_id") or "").strip() or None
        family = (row["node_id"].strip(), parent)
        positions[family] = positions.get(family, 0) + 1
        old_status = (row.get("status") or "new").strip()
        issues.append(Issue(
            issue_id=row["issue_id"].strip(), node_id=node.node_id, parent_issue_id=parent,
            title=row["title"].strip(), description=row["description"].strip(), status=parse_status(old_status),
            field_of_activity=node.field_of_activity, created_at=created_at, position=positions[family],
            metadata={"imported_from": SEED_SOURCE, "status_in_source": old_status},
        ))
    return issues


def load_progress_weights(path=WEIGHTS_FILE):
    rows = read_rows(path)
    if not rows or list(rows[0]) != WEIGHT_COLUMNS:
        raise ValueError(f"{path}: the columns must be {', '.join(WEIGHT_COLUMNS)}")
    try:
        return ProgressWeights.of({r["factor"].strip(): int(r["weight"]) for r in rows})
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from None
