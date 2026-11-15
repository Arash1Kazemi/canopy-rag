"""The organization model: NodeIdentifier, LayerIndex, Node, Layer, and the Hierarchy aggregate.

Hierarchy is the aggregate root. Every change to the tree goes through it, so it can guard the tree rules:
H02 (one root, each layer is its parent's layer plus 1) and H10 (a terminal node has no children).

The layer registry is part of the aggregate: each layer has a name, a role and a transfer rule (what it needs from the
nodes below it). A node's reporting format and minimum judge score are the rule of the layer that receives its packages.
When that rule exists, the hierarchy keeps the node's values equal to it (decision A16 in architecture/architecture.md).
"""
import re
from dataclasses import dataclass, replace
from typing import Optional

from ..shared.kernel import Confidentiality, DomainError, DomainEvent, TransferDetailLevel, TransferRule, parse_enum

ID_PATTERN = re.compile(r"[A-Za-z0-9_\-]+")
CHANGEABLE_DETAILS = ("name", "field_of_activity", "confidentiality", "reporting_format", "min_judge_score")


@dataclass(frozen=True)
class NodeIdentifier:
    """The stable id of a node, such as N4. It never changes and is never reused."""
    value: str

    def __post_init__(self):
        if not ID_PATTERN.fullmatch(self.value or ""):
            raise DomainError(f"a node id uses letters, digits, '_' or '-', not {self.value!r}")

    def __str__(self):
        return self.value


@dataclass(frozen=True)
class LayerIndex:
    """The position of a layer. Layer 0 is the top."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value < 0:
            raise DomainError(f"a layer index is a whole number from 0, not {self.value!r}")

    def below(self):
        return LayerIndex(self.value + 1)


@dataclass(frozen=True)
class Node:
    node_id: NodeIdentifier
    name: str
    layer: LayerIndex
    parent_id: Optional[NodeIdentifier]
    field_of_activity: str
    is_terminal: bool = False
    reporting_format: Optional[TransferDetailLevel] = None  # None for the root: it reports to nobody
    min_judge_score: Optional[int] = None
    confidentiality: Confidentiality = Confidentiality.INTERNAL

    def __post_init__(self):
        if not self.name.strip():
            raise DomainError(f"node {self.node_id} needs a name")
        if not self.field_of_activity.strip():
            raise DomainError(f"node {self.node_id} needs a field of activity")
        if self.min_judge_score is not None and not (isinstance(self.min_judge_score, int) and 1 <= self.min_judge_score <= 20):
            raise DomainError(f"node {self.node_id}: min_judge_score is a whole number from 1 to 20, not {self.min_judge_score!r}")


@dataclass(frozen=True)
class Layer:
    """A layer: its position, the nodes in it, and its registry entry (name, role, transfer rule).
    The rule says what this layer needs from the layer below; None means it receives nothing."""
    index: LayerIndex
    node_ids: tuple = ()
    name: str = ""
    role: str = ""
    rule: Optional[TransferRule] = None


class Hierarchy:
    """The whole tree of one organization. Build it root first, then each child after its parent."""

    def __init__(self):
        self._nodes = {}         # NodeIdentifier -> Node, in the order they were added
        self._definitions = {}   # layer index (int) -> Layer with no node ids: the layer registry
        self.events = []

    # --- changes to the tree
    def add_node(self, node):
        if node.node_id in self._nodes:
            raise DomainError(f"node {node.node_id} already exists; a node id is never reused")
        if node.parent_id is None:
            if self.root() is not None:
                raise DomainError(f"H02: the hierarchy already has a root ({self.root().node_id}); {node.node_id} needs a parent")
            if node.layer.value != 0:
                raise DomainError(f"H02: the root {node.node_id} must be in layer 0")
        else:
            parent = self._nodes.get(node.parent_id)
            if parent is None:
                raise DomainError(f"the parent {node.parent_id} of {node.node_id} does not exist yet; add it first")
            if parent.is_terminal:
                raise DomainError(f"H10: {parent.node_id} is a terminal node and cannot have the child {node.node_id}")
            if node.layer != parent.layer.below():
                raise DomainError(f"H02: {node.node_id} is in layer {node.layer.value}, "
                                  f"but its parent {parent.node_id} is in layer {parent.layer.value}")
            if self._definitions:
                self._require_rule(parent)
                self._require_node_matches_rule(node, self._rule_of(parent.layer.value))
        self._nodes[node.node_id] = node
        self.events.append(DomainEvent("NodeAdded", (("node_id", str(node.node_id)),)))
        return node

    def move_node(self, node_id, new_parent_id):
        """Give a node a new parent. Its whole subtree moves with it and shifts layers by the same amount (decision A17).
        Returns the ids of the nodes that moved, the node first."""
        node, new_parent = self.node(node_id), self.node(new_parent_id)
        if node.parent_id is None:
            raise DomainError(f"H02: the root {node.node_id} cannot move")
        below = self.descendants(node.node_id)
        if new_parent.node_id == node.node_id or new_parent.node_id in {n.node_id for n in below}:
            raise DomainError(f"{node.node_id} cannot move under itself or under one of its own descendants ({new_parent.node_id})")
        if new_parent.node_id == node.parent_id:
            raise DomainError(f"{node.node_id} is already under {new_parent.node_id}")
        if new_parent.is_terminal:
            raise DomainError(f"H10: {new_parent.node_id} is a terminal node and cannot have the child {node.node_id}")
        if self._definitions:
            self._require_rule(new_parent)
        shift = new_parent.layer.value + 1 - node.layer.value
        moved = [node] + below
        before = {n.node_id: n for n in moved}
        for n in moved:
            parent_id = new_parent.node_id if n.node_id == node.node_id else n.parent_id
            self._nodes[n.node_id] = replace(n, layer=LayerIndex(n.layer.value + shift), parent_id=parent_id)
        rederived = self._rederive([n.node_id for n in moved])
        self.events.append(DomainEvent("NodeMoved", (
            ("node_id", str(node.node_id)), ("from_parent", str(node.parent_id)), ("to_parent", str(new_parent.node_id)),
            ("layer_shift", str(shift)), ("moved", " ".join(str(n.node_id) for n in moved)),
            ("reporting_rederived", " ".join(str(i) for i in rederived)))))
        return [n.node_id for n in moved]

    def set_terminal(self, node_id, is_terminal):
        """Make a node a terminal node (a black box), or open it again. H10, first half: a terminal node has no children.
        The second half (one summary document) spans two aggregates, so the workflow checks it."""
        node = self.node(node_id)
        if is_terminal and self.children(node.node_id):
            raise DomainError(f"H10: {node.node_id} has children, so it cannot become a terminal node")
        if node.is_terminal == is_terminal:
            return node
        updated = replace(node, is_terminal=is_terminal)
        self._nodes[node.node_id] = updated
        self.events.append(DomainEvent("NodeTerminalChanged", (("node_id", str(node.node_id)), ("is_terminal", str(is_terminal).lower()))))
        return updated

    def change_details(self, node_id, /, **changes):
        """Change a node's name, field of activity, confidentiality, reporting format or minimum judge score.
        Its id, layer and parent do not change here (a move changes layer and parent). When a transfer rule sets the
        reporting format or the minimum score, change the rule instead."""
        node = self.node(node_id)
        unknown = sorted(set(changes) - set(CHANGEABLE_DETAILS))
        if unknown:
            raise DomainError(f"{', '.join(unknown)} cannot be changed here; only {', '.join(CHANGEABLE_DETAILS)} can. "
                              f"A node's id never changes, and its layer and parent change through a move")
        rule = self.receiving_rule(node.node_id)
        if rule is not None and "reporting_format" in changes:
            raise DomainError(f"{node.node_id}'s reporting format is set by the transfer rule of layer {node.layer.value - 1}; change the rule instead")
        if rule is not None and rule.min_judge_score is not None and "min_judge_score" in changes:
            raise DomainError(f"{node.node_id}'s minimum judge score is set by the transfer rule of layer {node.layer.value - 1}; change the rule instead")
        values = dict(changes)
        if "confidentiality" in values:
            values["confidentiality"] = parse_enum(Confidentiality, values["confidentiality"], "confidentiality")
        if values.get("reporting_format") is not None:
            values["reporting_format"] = parse_enum(TransferDetailLevel, values["reporting_format"], "reporting_format")
        updated = replace(node, **values)       # Node revalidates the name, the field and the score
        if updated == node:
            return node
        self._nodes[node.node_id] = updated
        self.events.append(DomainEvent("NodeDetailsChanged", (("node_id", str(node.node_id)), ("fields", " ".join(sorted(values))))))
        return updated

    # --- changes to the layer registry
    def define_layer(self, index, name, role="", rule=None):
        index = index if isinstance(index, LayerIndex) else LayerIndex(index)
        if index.value in self._definitions:
            raise DomainError(f"layer {index.value} is already defined; change its rule with set_layer_rule")
        if not name.strip():
            raise DomainError(f"layer {index.value} needs a name")
        if rule is not None and not isinstance(rule, TransferRule):
            raise DomainError(f"layer {index.value}: the rule must be a TransferRule")
        self._definitions[index.value] = Layer(index, (), name.strip(), role.strip(), rule)
        self.events.append(DomainEvent("LayerDefined", (("layer", str(index.value)),)))

    def set_layer_rule(self, index, rule):
        """Replace a layer's transfer rule. The nodes that send into this layer take the new detail level and minimum
        score. If the result breaks a registry rule, nothing changes and the error says which."""
        index = index if isinstance(index, LayerIndex) else LayerIndex(index)
        definition = self._definitions.get(index.value)
        if definition is None:
            raise DomainError(f"layer {index.value} is not defined; define it first")
        saved_definitions, saved_nodes = dict(self._definitions), dict(self._nodes)
        self._definitions[index.value] = replace(definition, rule=rule)
        try:
            senders = [n.node_id for n in self._nodes.values() if n.layer.value == index.value + 1]
            self._rederive(senders)
            found = self.problems()
            if found:
                raise DomainError("that rule breaks the layer registry: " + "; ".join(found))
        except DomainError:
            self._definitions, self._nodes = saved_definitions, saved_nodes
            raise
        self.events.append(DomainEvent("LayerRuleChanged", (("layer", str(index.value)),)))

    # --- questions
    def node(self, node_id):
        key = node_id if isinstance(node_id, NodeIdentifier) else NodeIdentifier(node_id)
        try:
            return self._nodes[key]
        except KeyError:
            raise DomainError(f"unknown node {key}") from None

    def has(self, node_id):
        return NodeIdentifier(str(node_id)) in self._nodes

    def nodes(self):
        return list(self._nodes.values())

    def root(self):
        return next((n for n in self._nodes.values() if n.parent_id is None), None)

    def children(self, node_id):
        key = self.node(node_id).node_id
        return [n for n in self._nodes.values() if n.parent_id == key]

    def parent(self, node_id):
        node = self.node(node_id)
        return None if node.parent_id is None else self._nodes[node.parent_id]

    def path(self, node_id):
        """The nodes from the root down to this node, for example N0 > N1 > N4 > N6."""
        return list(reversed([self.node(node_id)] + self.ancestors(node_id)))

    def ancestors(self, node_id):
        """The parent, then its parent, up to the root."""
        chain, node = [], self.parent(node_id)
        while node is not None:
            chain.append(node)
            node = self.parent(node.node_id)
        return chain

    def descendants(self, node_id):
        """Every node below this one, level by level (breadth first)."""
        found, queue = [], self.children(node_id)
        while queue:
            node = queue.pop(0)
            found.append(node)
            queue.extend(self.children(node.node_id))
        return found

    def siblings(self, node_id):
        node = self.node(node_id)
        if node.parent_id is None:
            return []
        return [n for n in self.children(node.parent_id) if n.node_id != node.node_id]

    def nodes_in_layer(self, index):
        value = index.value if isinstance(index, LayerIndex) else index
        return [n for n in self._nodes.values() if n.layer.value == value]

    def terminal_nodes(self):
        return [n for n in self._nodes.values() if n.is_terminal]

    def layers(self):
        """Every layer that has nodes or a registry entry, from the top, with its nodes."""
        by_index = {}
        for n in self._nodes.values():
            by_index.setdefault(n.layer.value, []).append(n.node_id)
        result = []
        for i in sorted(set(by_index) | set(self._definitions)):
            definition = self._definitions.get(i, Layer(LayerIndex(i)))
            result.append(replace(definition, node_ids=tuple(by_index.get(i, ()))))
        return result

    def layer_definition(self, index):
        value = index.value if isinstance(index, LayerIndex) else index
        return self._definitions.get(value)

    def receiving_rule(self, node_id):
        """The transfer rule that applies to the packages this node sends: the rule of its parent's layer.
        None for the root, or when that layer has no registry entry or no rule."""
        node = self.node(node_id)
        if node.parent_id is None:
            return None
        return self._rule_of(self._nodes[node.parent_id].layer.value)

    def problems(self):
        """Where the nodes and the layer registry disagree, as plain sentences. Empty means consistent."""
        found = []
        if self._definitions:
            for layer in self.layers():
                if layer.node_ids and layer.index.value not in self._definitions:
                    found.append(f"layer {layer.index.value} has nodes but is not in the layer registry")
            for i in sorted(self._definitions):
                if self.nodes_in_layer(i + 1) and self._rule_of(i) is None:
                    found.append(f"layer {i} receives packages from layer {i + 1} but has no transfer rule")
                above, below = self._rule_of(i), self._rule_of(i + 1)
                if above and below and above.detail_level.rank > below.detail_level.rank:
                    found.append(f"layer {i} asks for more detail ({above.detail_level.value}) than layer {i + 1} "
                                 f"({below.detail_level.value}), but detail gets coarser going up")
        for n in self._nodes.values():
            rule = self.receiving_rule(n.node_id)
            if rule is not None:
                if n.reporting_format != rule.detail_level:
                    found.append(f"{n.node_id} sends {n.reporting_format.value if n.reporting_format else 'nothing'}, "
                                 f"but the rule of layer {n.layer.value - 1} asks for {rule.detail_level.value}")
                if rule.min_judge_score is not None and n.min_judge_score != rule.min_judge_score:
                    found.append(f"{n.node_id} has minimum judge score {n.min_judge_score}, "
                                 f"but the rule of layer {n.layer.value - 1} says {rule.min_judge_score}")
            parent = self.parent(n.node_id)
            if parent and parent.reporting_format and n.reporting_format and parent.reporting_format.rank > n.reporting_format.rank:
                found.append(f"{n.node_id} sends less detail than its parent {parent.node_id}, but detail gets coarser going up")
        return found

    def check_complete(self):
        """A finished hierarchy has exactly one root and no disagreement between the nodes and the layer registry."""
        if self.root() is None:
            raise DomainError("H02: the hierarchy has no root")
        found = self.problems()
        if found:
            raise DomainError("the nodes and the layer registry disagree: " + "; ".join(found))

    # --- inside
    def _rule_of(self, layer_value):
        definition = self._definitions.get(layer_value)
        return None if definition is None else definition.rule

    def _require_rule(self, parent):
        if self._rule_of(parent.layer.value) is None:
            raise DomainError(f"layer {parent.layer.value} has no transfer rule, so a node under {parent.node_id} "
                              f"could not send it packages; set the rule of layer {parent.layer.value} first")

    def _require_node_matches_rule(self, node, rule):
        if node.reporting_format != rule.detail_level:
            raise DomainError(f"{node.node_id} sends {node.reporting_format.value if node.reporting_format else 'nothing'}, "
                              f"but the transfer rule of layer {node.layer.value - 1} asks for {rule.detail_level.value}")
        if rule.min_judge_score is not None and node.min_judge_score != rule.min_judge_score:
            raise DomainError(f"{node.node_id} has minimum judge score {node.min_judge_score}, "
                              f"but the transfer rule of layer {node.layer.value - 1} says {rule.min_judge_score}")

    def _rederive(self, node_ids):
        """Give each node the detail level and minimum score of the rule that receives its packages. Returns the ids changed."""
        changed = []
        for node_id in node_ids:
            node = self._nodes[node_id]
            rule = self.receiving_rule(node_id)
            if rule is None:
                continue
            score = rule.min_judge_score if rule.min_judge_score is not None else node.min_judge_score
            if (node.reporting_format, node.min_judge_score) != (rule.detail_level, score):
                self._nodes[node_id] = replace(node, reporting_format=rule.detail_level, min_judge_score=score)
                changed.append(node_id)
        return changed
