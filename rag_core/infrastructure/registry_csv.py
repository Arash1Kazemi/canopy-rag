"""Load the Hierarchy from registry/node_layer_registry.csv and, optionally, registry/layer_registry.csv.

The same rows (as dictionaries of text) are also what the SQLite hierarchy repository reads and writes, so one function
builds the Hierarchy from rows whatever the source is.
"""
import csv
from pathlib import Path

from ..organization.model import Hierarchy, LayerIndex, Node, NodeIdentifier
from ..shared.kernel import Confidentiality, DomainError, TransferDetailLevel, TransferRule, parse_enum

NODE_COLUMNS = ["node_id", "name", "layer_index", "parent_node_id", "field_of_activity", "is_terminal",
                "reporting_format", "min_judge_score", "confidentiality"]
LAYER_COLUMNS = ["layer_index", "name", "role", "detail_level", "min_judge_score", "required_topics", "excluded_topics",
                 "required_fields", "output_format", "max_words", "citation_level", "source"]


def _whole_number(text, what):
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        raise DomainError(f"{what} must be a whole number, not {text!r}") from None


def _list(text):
    return tuple(part.strip() for part in text.split(";") if part.strip())


def node_from_row(row):
    fmt = row["reporting_format"].strip()
    return Node(
        node_id=NodeIdentifier(row["node_id"]),
        name=row["name"],
        layer=LayerIndex(int(row["layer_index"])),
        parent_id=NodeIdentifier(row["parent_node_id"]) if row["parent_node_id"].strip() else None,
        field_of_activity=row["field_of_activity"],
        is_terminal=row["is_terminal"].strip().lower() == "true",
        reporting_format=None if fmt in ("", "none") else parse_enum(TransferDetailLevel, fmt, "reporting_format"),
        min_judge_score=_whole_number(row["min_judge_score"], "min_judge_score"),
        confidentiality=parse_enum(Confidentiality, row["confidentiality"], "confidentiality"),
    )


def row_of_node(node):
    return {"node_id": str(node.node_id), "name": node.name, "layer_index": str(node.layer.value),
            "parent_node_id": str(node.parent_id) if node.parent_id else "", "field_of_activity": node.field_of_activity,
            "is_terminal": "true" if node.is_terminal else "false",
            "reporting_format": node.reporting_format.value if node.reporting_format else "none",
            "min_judge_score": "" if node.min_judge_score is None else str(node.min_judge_score),
            "confidentiality": node.confidentiality.value}


def rule_from_row(row):
    """A layer row with an empty detail_level receives nothing, so it has no rule."""
    level = row["detail_level"].strip()
    if not level:
        return None
    return TransferRule(
        detail_level=parse_enum(TransferDetailLevel, level, "detail_level"),
        min_judge_score=_whole_number(row["min_judge_score"], "min_judge_score"),
        required_topics=_list(row["required_topics"]),
        excluded_topics=_list(row["excluded_topics"]),
        required_fields=_list(row["required_fields"]),
        output_format=row["output_format"].strip(),
        max_words=_whole_number(row["max_words"], "max_words"),
        citation_level=row["citation_level"].strip() or None,
    )


def row_of_layer(layer):
    rule = layer.rule
    return {"layer_index": str(layer.index.value), "name": layer.name, "role": layer.role,
            "detail_level": rule.detail_level.value if rule else "",
            "min_judge_score": "" if rule is None or rule.min_judge_score is None else str(rule.min_judge_score),
            "required_topics": ";".join(rule.required_topics) if rule else "",
            "excluded_topics": ";".join(rule.excluded_topics) if rule else "",
            "required_fields": ";".join(rule.required_fields) if rule else "",
            "output_format": rule.output_format if rule else "",
            "max_words": "" if rule is None or rule.max_words is None else str(rule.max_words),
            "citation_level": (rule.citation_level or "") if rule else ""}


def hierarchy_from_rows(node_rows, layer_rows=()):
    """Layers are defined first, so that adding a node can check it against the rule of its parent's layer.
    Nodes are added parents before children, whatever the row order is."""
    hierarchy = Hierarchy()
    for row in layer_rows:
        hierarchy.define_layer(int(row["layer_index"]), row["name"], row["role"], rule_from_row(row))
    pending = list(node_rows)
    while pending:
        ready = [r for r in pending if not r["parent_node_id"].strip() or hierarchy.has(r["parent_node_id"])]
        if not ready:
            raise DomainError(f"these nodes have a parent that is not in the registry: {[r['node_id'] for r in pending]}")
        for r in ready:
            hierarchy.add_node(node_from_row(r))
        pending = [r for r in pending if r not in ready]
    hierarchy.check_complete()
    return hierarchy


def _read(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class CsvHierarchyRepository:
    """`layers_path` is optional: without it the hierarchy has no layer registry (names, roles and transfer rules)."""

    def __init__(self, path, layers_path=None):
        self.path = Path(path)
        self.layers_path = Path(layers_path) if layers_path else None

    def load(self):
        layer_rows = _read(self.layers_path) if self.layers_path else []
        return hierarchy_from_rows(_read(self.path), layer_rows)
