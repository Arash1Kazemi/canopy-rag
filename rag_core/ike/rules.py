"""Rules that need to see several relations, or other parts of the system, before a relation is saved.

1. The node exists. It is checked through the node directory, never by comparing strings.
2. No duplicate edge: the same type, source and target is stored once (for "similar", in either direction).
3. An issue, an answer (the answer of an issue) and a knowledge item belong to one node, so they appear only in
   relations of that node. An executor may appear in another node's relation (the 18 June minutes of N6 list a fleet
   manager of N4), but an edge whose only other side is a label or a project belongs to the executor's own node.
   These checks run when a lookup is given; a lookup takes an id and returns its node id, or None when it is unknown.
4. An issue decomposes into a sub-issue at most once (a sub-issue has one parent, proposal 12.2), and neither
   "decomposes into" nor "blocked by" may form a cycle (as for issues, decision A33).
"""
from ..shared.kernel import DomainError
from .model import ACYCLIC, RefKind, RelationType

NODE_OWNED = {RefKind.ISSUE: "issue", RefKind.ANSWER: "issue", RefKind.KNOWLEDGE_ITEM: "item"}
EXECUTOR_ONLY = (RelationType.EXECUTOR_HAS_EXPERTISE, RelationType.EXECUTOR_WORKED_ON_PROJECT)


def check_relations(new_relations, existing, nodes, *, issue_node=None, item_node=None, executor_node=None):
    """Check new relations against the stored ones. Raises DomainError naming the first broken rule.

    `existing` is any iterable of stored relations, `nodes` a NodeDirectory. The lookups are optional callables:
    issue_node("I01") -> "N6" or None, item_node("D11") -> "N6" or None, executor_node("P03") -> "N6" or None."""
    new_relations = list(new_relations)
    stored = list(existing)
    seen = {r.edge_key for r in stored}
    for relation in new_relations:
        if relation.edge_key in seen:
            raise DomainError(f"duplicate relation: {_describe(relation)} is already in the IKE model")
        seen.add(relation.edge_key)
    lookups = {"issue": issue_node, "item": item_node}
    for relation in new_relations:
        nodes.require(relation.node_id)        # UnknownNodeError (a DomainError) for an unknown node
        for side in (relation.source, relation.target):
            lookup = lookups.get(NODE_OWNED.get(side.kind))
            if lookup is not None:
                _same_node(relation, side, lookup(side.key))
            if side.kind == RefKind.EXECUTOR and executor_node is not None:
                home = executor_node(side.key)
                if home is None:
                    raise DomainError(f"{_describe(relation)}: executor {side.key} does not exist")
                if relation.relation_type in EXECUTOR_ONLY and str(home) != str(relation.node_id):
                    raise DomainError(f"{_describe(relation)}: executor {side.key} belongs to {home}, "
                                      f"so this relation belongs to {home}, not {relation.node_id}")
    world = stored + new_relations
    _check_one_parent(new_relations, world)
    for relation_type in ACYCLIC:
        _check_no_cycle(relation_type, [r for r in new_relations if r.relation_type == relation_type], world)


def _same_node(relation, side, home):
    what = "the answer of issue" if side.kind == RefKind.ANSWER else side.kind.value.replace("_", " ")
    if home is None:
        raise DomainError(f"{_describe(relation)}: {what} {side.key} does not exist")
    if str(home) != str(relation.node_id):
        raise DomainError(f"{_describe(relation)}: {what} {side.key} belongs to {home}, and a relation stays "
                          f"inside one node ({relation.node_id})")


def _check_one_parent(new_relations, world):
    decomposes = RelationType.ISSUE_DECOMPOSES_INTO_ISSUE
    for relation in new_relations:
        if relation.relation_type != decomposes:
            continue
        parents = {r.source.key for r in world if r.relation_type == decomposes and r.target == relation.target}
        if len(parents) > 1:
            raise DomainError(f"{_describe(relation)}: issue {relation.target.key} would have two parents "
                              f"({', '.join(sorted(parents))}); a sub-issue has one parent")


def _check_no_cycle(relation_type, new_relations, world):
    links = {}
    for r in world:
        if r.relation_type == relation_type:
            links.setdefault(r.source.key, set()).add(r.target.key)
    for relation in new_relations:
        stack, seen = [relation.target.key], set()
        while stack:
            current = stack.pop()
            if current == relation.source.key:
                raise DomainError(f"{_describe(relation)}: the '{relation_type.phrase}' links would make a cycle")
            if current not in seen:
                seen.add(current)
                stack.extend(links.get(current, ()))


def _describe(relation):
    return f"{relation.source} {relation.relation_type.value} {relation.target}"
