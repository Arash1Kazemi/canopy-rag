"""Rules that need to see several issues at once, and the relative position of an issue (proposal 12.2 and 12.3).

These are domain functions, not an aggregate: each issue is its own aggregate root, and a rule that spans issues is
checked here before the use case saves anything.

1. The node exists. It is checked through the node directory, never by comparing strings (decision A23).
2. A sub-issue is in its parent's node, and "blocked by" links stay inside one node too (decision A33).
3. No cycles: an issue is never its own ancestor, and never waits on itself through a chain of "blocked by" links.
4. Siblings (same node, same parent) have different positions.
"""
from dataclasses import dataclass

from ..shared.kernel import DomainError
from .model import as_issue_id


def check_issues(new_issues, existing, nodes):
    """Check new or changed issues against the stored ones. `existing` is any iterable of stored issues; `nodes` is a
    NodeDirectory. New issues may refer to each other (a parent and its sub-issues saved together). Raises DomainError."""
    world = {i.issue_id: i for i in existing}
    for issue in new_issues:
        world[issue.issue_id] = issue
    for issue in new_issues:
        nodes.require(issue.node_id)          # UnknownNodeError (a DomainError) for an unknown node
        if issue.parent_issue_id is not None:
            parent = world.get(issue.parent_issue_id)
            if parent is None:
                raise DomainError(f"issue {issue.issue_id}: its parent {issue.parent_issue_id} does not exist")
            if parent.node_id != issue.node_id:
                raise DomainError(f"issue {issue.issue_id}: a sub-issue stays in its parent's node "
                                  f"({issue.parent_issue_id} is in {parent.node_id}, not {issue.node_id})")
        for blocker_id in issue.blocked_by:
            blocker = world.get(blocker_id)
            if blocker is None:
                raise DomainError(f"issue {issue.issue_id}: the blocking issue {blocker_id} does not exist")
            if blocker.node_id != issue.node_id:
                raise DomainError(f"issue {issue.issue_id}: a 'blocked by' link stays inside one node "
                                  f"({blocker_id} is in {blocker.node_id}, not {issue.node_id})")
    for issue in new_issues:
        _check_no_parent_cycle(issue, world)
        _check_no_blocking_cycle(issue, world)
    _check_positions(new_issues, world)


def _check_no_parent_cycle(issue, world):
    seen = {issue.issue_id}
    current = issue
    while current.parent_issue_id is not None:
        if current.parent_issue_id in seen:
            raise DomainError(f"issue {issue.issue_id}: the parent links make a cycle through {current.parent_issue_id}")
        seen.add(current.parent_issue_id)
        current = world[current.parent_issue_id]


def _check_no_blocking_cycle(issue, world):
    """Walk every chain of 'blocked by' links from the issue; coming back to it is a cycle."""
    stack, seen = list(issue.blocked_by), set()
    while stack:
        current = stack.pop()
        if current == issue.issue_id:
            raise DomainError(f"issue {issue.issue_id}: the 'blocked by' links make a cycle (it would wait on itself)")
        if current in seen:
            continue
        seen.add(current)
        stack.extend(world[current].blocked_by)


def _check_positions(new_issues, world):
    for issue in new_issues:
        for other in world.values():
            if other.issue_id != issue.issue_id and _same_family(issue, other) and other.position == issue.position:
                raise DomainError(f"issue {issue.issue_id}: position {issue.position} is already taken by its sibling {other.issue_id}")


def _same_family(a, b):
    return a.node_id == b.node_id and a.parent_issue_id == b.parent_issue_id


def sibling_order(issues):
    """Issues in sibling order: by position, then by id so the order is the same on every run."""
    return sorted(issues, key=lambda i: (i.position, i.issue_id.number))


def next_position(parent_id, node_id, issues):
    """The first free position at the end of a family of siblings."""
    taken = [i.position for i in issues if i.node_id == node_id and i.parent_issue_id == parent_id]
    return max(taken, default=0) + 1


def next_issue_id(issues):
    """The next free id after the highest one, keeping two digits as the case study does (I08, I09, I10, ...)."""
    highest = max((i.issue_id.number for i in issues), default=0)
    return as_issue_id(f"I{highest + 1:02d}")


@dataclass(frozen=True)
class RelativePosition:
    """Where an issue stands among the issues of its node (proposal 12.3).

    position: its place among its siblings (1 is first). siblings: the others with the same parent, in order.
    children: its sub-issues in order. blocked_by: what it waits on. blocks: what waits on it.
    same_category: other issues of the node with the same category (empty when it has no category).
    """
    issue_id: object
    node_id: object
    parent_id: object
    position: int
    siblings: tuple
    children: tuple
    blocked_by: tuple
    blocks: tuple
    same_category: tuple


def relative_position(issue_id, issues):
    """The RelativePosition of one issue. Only issues of the same node are looked at."""
    issue_id = as_issue_id(issue_id)
    by_id = {i.issue_id: i for i in issues}
    if issue_id not in by_id:
        raise DomainError(f"unknown issue {issue_id}")
    me = by_id[issue_id]
    mine = [i for i in by_id.values() if i.node_id == me.node_id]
    ids = lambda group: tuple(i.issue_id for i in sibling_order(group))
    return RelativePosition(
        issue_id=me.issue_id, node_id=me.node_id, parent_id=me.parent_issue_id, position=me.position,
        siblings=ids(i for i in mine if i.parent_issue_id == me.parent_issue_id and i.issue_id != me.issue_id),
        children=ids(i for i in mine if i.parent_issue_id == me.issue_id),
        blocked_by=tuple(sorted(me.blocked_by, key=lambda x: x.number)),
        blocks=ids(i for i in mine if me.issue_id in i.blocked_by),
        same_category=ids(i for i in mine if me.category and i.category == me.category and i.issue_id != me.issue_id),
    )
