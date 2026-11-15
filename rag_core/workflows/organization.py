"""The node and layer workflows (Phase 6): define a node, move a node, make a node terminal, change a node, set a layer's rule.

Each workflow loads the hierarchy, changes it through the aggregate, checks it is still consistent, and saves it only
then. Like ingestion, a workflow never raises for a broken rule: the result says what went wrong and nothing is saved,
so a bad request cannot leave the stored hierarchy half changed.

Layer membership (which layer a node belongs to) is never chosen: it follows from the parent, so you choose the parent.
A workflow sits in the application layer because one rule spans two aggregates. H10 says a terminal node has no children
(Hierarchy) and exactly one summary document (KnowledgeItem), so making a node terminal checks both.
"""
from dataclasses import dataclass

from ..organization.model import Node, NodeIdentifier
from ..shared.kernel import Confidentiality, DomainError, TransferDetailLevel, parse_enum

NODE_DEFINED, NODE_MOVED, NODE_CHANGED = "node defined", "node moved", "node changed"
TERMINAL_CHANGED, LAYER_DEFINED, LAYER_RULE_SET, FAILED = "terminal changed", "layer defined", "layer rule set", "failed"


@dataclass(frozen=True)
class WorkflowResult:
    outcome: str
    detail: str = ""
    node_ids: tuple = ()

    @property
    def ok(self):
        return self.outcome != FAILED


class OrganizationService:
    def __init__(self, repository, knowledge=None):
        """`repository` loads and saves the Hierarchy. `knowledge` is a KnowledgeRepository, needed only to make a node terminal."""
        self.repo = repository
        self.knowledge = knowledge

    def define_node(self, node_id, name, parent_id, field_of_activity, is_terminal=False, confidentiality="internal",
                    reporting_format=None, min_judge_score=None):
        def change(h):
            parent = h.node(parent_id)
            if parent.is_terminal:
                raise DomainError(f"H10: {parent.node_id} is a terminal node and cannot have the child {node_id}")
            definition = h.layer_definition(parent.layer)
            rule = definition.rule if definition else None
            if rule is not None:
                if reporting_format and parse_enum(TransferDetailLevel, reporting_format, "reporting_format") != rule.detail_level:
                    raise DomainError(f"the transfer rule of layer {parent.layer.value} asks for {rule.detail_level.value} packages, "
                                      f"so the reporting format is not chosen here")
                fmt = rule.detail_level
                score = rule.min_judge_score if rule.min_judge_score is not None else min_judge_score
                if score is None:
                    raise DomainError(f"the rule of layer {parent.layer.value} sets no minimum judge score: give min_judge_score")
            else:
                if not reporting_format or min_judge_score is None:
                    raise DomainError(f"layer {parent.layer.value} has no transfer rule: give reporting_format and min_judge_score")
                fmt, score = parse_enum(TransferDetailLevel, reporting_format, "reporting_format"), min_judge_score
            node = Node(NodeIdentifier(node_id), name, parent.layer.below(), parent.node_id, field_of_activity,
                        is_terminal=is_terminal, reporting_format=fmt, min_judge_score=score,
                        confidentiality=parse_enum(Confidentiality, confidentiality, "confidentiality"))
            h.add_node(node)
            origin = f" (from the rule of layer {parent.layer.value})" if rule is not None else ""
            return WorkflowResult(NODE_DEFINED, f"{node.node_id} is in layer {node.layer.value} under {parent.node_id}; "
                                                f"it sends {fmt.value} packages with minimum judge score {score}{origin}", (str(node.node_id),))
        return self._change(change)

    def move_node(self, node_id, new_parent_id):
        def change(h):
            before = {n.node_id: n for n in h.nodes()}
            moved = h.move_node(node_id, new_parent_id)
            lines = []
            for key in moved:
                old, new = before[key], h.node(key)
                note = f"{key}: layer {old.layer.value} -> {new.layer.value}"
                if old.reporting_format != new.reporting_format:
                    note += f", now sends {new.reporting_format.value} instead of {old.reporting_format.value}"
                lines.append(note)
            return WorkflowResult(NODE_MOVED, f"{node_id} is now under {new_parent_id}. " + "; ".join(lines), tuple(str(k) for k in moved))
        return self._change(change)

    def set_terminal(self, node_id, is_terminal=True):
        def change(h):
            h.set_terminal(node_id, is_terminal)        # the tree half of H10 first: a terminal node has no children
            if is_terminal:                             # then the document half. Nothing is saved unless both hold.
                if self.knowledge is None:
                    raise DomainError("give the knowledge database, so the second half of H10 (one summary document) can be checked")
                count = len(self.knowledge.items_of_node(str(h.node(node_id).node_id)))
                if count > 1:
                    raise DomainError(f"H10: {node_id} has {count} knowledge items, but a terminal node has one summary document")
            return WorkflowResult(TERMINAL_CHANGED, f"{node_id} is {'now' if is_terminal else 'no longer'} a terminal node", (node_id,))
        return self._change(change)

    def change_node(self, node_id, /, **changes):
        def change(h):
            h.change_details(node_id, **changes)
            return WorkflowResult(NODE_CHANGED, f"{node_id}: changed {', '.join(sorted(changes))}", (node_id,))
        return self._change(change)

    def define_layer(self, index, name, role="", rule=None):
        def change(h):
            h.define_layer(index, name, role, rule)
            return WorkflowResult(LAYER_DEFINED, f"layer {index} is defined: {name}")
        return self._change(change)

    def set_layer_rule(self, index, rule):
        def change(h):
            before = {n.node_id: n for n in h.nodes()}
            h.set_layer_rule(index, rule)
            updated = [str(n.node_id) for n in h.nodes() if n != before[n.node_id]]
            return WorkflowResult(LAYER_RULE_SET, f"layer {index} now needs {rule.detail_level.value} packages"
                                                  + (f"; updated nodes: {', '.join(updated)}" if updated else ""), tuple(updated))
        return self._change(change)

    def _change(self, change):
        try:
            hierarchy = self.repo.load()
            result = change(hierarchy)
            hierarchy.check_complete()
            self.repo.save(hierarchy)
            return result
        except DomainError as error:
            return WorkflowResult(FAILED, str(error))
