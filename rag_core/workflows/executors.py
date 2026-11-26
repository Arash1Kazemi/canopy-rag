"""The executor workflows (Phase 9, proposal section 13): register executors, match an issue to executors with an
explained score, and map an executor to an issue (or take the mapping away).

Like the issue workflows, a change never raises for a broken rule: the result says what went wrong and nothing is saved.
Every workflow gets its repositories, node directory and match weights as arguments, so unit tests pass test doubles.

Mapping an executor to an issue puts the executor's id in the issue's `executor_ids`. That is the fact the progress
rule "an executor is mapped" (14.1, factor executor_mapped) reads, so progress changes without any change to the weights.

Where to look for executors (decision X1, to confirm): the default scope is "node", the executors of the issue's own
node only, like the comparison of issues (12.1) and the node filter of retrieval (H01). The scope "lineage" also takes the
executors of the ancestors and the descendants of that node, so a person at the Transit Agency can be proposed for an
issue of a project below it. Siblings and cousins are never candidates. Mapping accepts any executor of the lineage.
"""
from dataclasses import dataclass

from ..executors.matching import rank_executors
from ..executors.model import as_executor_id
from ..issues.model import as_issue_id
from ..shared.kernel import DomainError

SCOPES = ("node", "lineage")
IMPORTED, MATCHED, MAPPED, UNMAPPED, REGISTERED, FAILED = "imported", "matched", "mapped", "unmapped", "registered", "failed"


@dataclass(frozen=True)
class ExecutorResult:
    outcome: str
    detail: str = ""
    executor_ids: tuple = ()
    matches: tuple = ()

    @property
    def ok(self):
        return self.outcome != FAILED


class ExecutorService:
    def __init__(self, executors, issues, nodes, weights, hierarchy=None):
        """`executors` is an ExecutorRepository, `issues` an IssueRepository, `nodes` a NodeDirectory, `weights` the
        MatchWeights (config/executor_match_weights.csv). `hierarchy` is a function that returns the Hierarchy (for
        example `hierarchy_repository.load`); it is needed only for the scope "lineage"."""
        self.executors = executors
        self.issues = issues
        self.nodes = nodes
        self.weights = weights
        self.hierarchy = hierarchy

    # --- changes -----------------------------------------------------------------------------------------------
    def import_seed(self, executors):
        """Store the seed executors that are not stored yet (the ids stay as they are). Running it twice adds nothing new."""
        def change():
            for executor in executors:
                self.nodes.require(executor.node_id)
            new = [e for e in executors if self.executors.get(e.executor_id) is None]
            self.executors.add_all(new)
            ids = tuple(str(e.executor_id) for e in new)
            return ExecutorResult(IMPORTED, f"{len(new)} executor(s) imported, {len(executors) - len(new)} already stored", ids)
        return self._attempt(change)

    def register_executor(self, executor):
        """Add one executor (a person, or an organizational capability). Its node must exist."""
        def change():
            self.nodes.require(executor.node_id)
            self.executors.add_all([executor])
            return ExecutorResult(REGISTERED, f"{executor.executor_id} {executor.name} is registered in {executor.node_id}",
                                  (str(executor.executor_id),))
        return self._attempt(change)

    def map_executor(self, issue_id, executor_id):
        """Map an executor to an issue. The executor must be in the issue's lineage (its node, ancestors or descendants)."""
        def change():
            issue, executor = self._require_issue(issue_id), self._require_executor(executor_id)
            allowed = self._lineage(issue.node_id) if self.hierarchy is not None else {issue.node_id}
            if executor.node_id not in allowed:
                raise DomainError(f"executor {executor.executor_id} is in {executor.node_id}, which is not the node of issue "
                                  f"{issue.issue_id} ({issue.node_id}) or above or below it")
            if str(executor.executor_id) in issue.executor_ids:
                raise DomainError(f"executor {executor.executor_id} is already mapped to issue {issue.issue_id}")
            self.issues.update(issue.with_changes(executor_ids=issue.executor_ids + (str(executor.executor_id),)))
            return ExecutorResult(MAPPED, f"{executor.executor_id} {executor.name} is now mapped to {issue.issue_id}",
                                  (str(executor.executor_id),))
        return self._attempt(change)

    def unmap_executor(self, issue_id, executor_id):
        def change():
            issue, key = self._require_issue(issue_id), str(as_executor_id(executor_id))
            if key not in issue.executor_ids:
                raise DomainError(f"executor {key} is not mapped to issue {issue.issue_id}")
            self.issues.update(issue.with_changes(executor_ids=tuple(e for e in issue.executor_ids if e != key)))
            return ExecutorResult(UNMAPPED, f"{key} is no longer mapped to {issue.issue_id}", (key,))
        return self._attempt(change)

    # --- questions ---------------------------------------------------------------------------------------------
    def match_executors(self, issue_id, scope="node", limit=None, include_unmatched=False):
        """Rank executors for an issue, each with the explanation of its score. Nothing is saved."""
        def change():
            if scope not in SCOPES:
                raise DomainError(f"scope must be one of {', '.join(SCOPES)}, not {scope!r}")
            if limit is not None and (not isinstance(limit, int) or limit < 1):
                raise DomainError(f"limit is a whole number from 1, not {limit!r}")
            issue = self._require_issue(issue_id)
            nodes = {issue.node_id} if scope == "node" else self._lineage(issue.node_id)
            candidates = [e for e in self.executors.all_executors() if e.node_id in nodes]
            ranked = rank_executors(issue, candidates, self.weights, include_unmatched)
            ranked = tuple(ranked if limit is None else ranked[:limit])
            return ExecutorResult(MATCHED, f"{len(ranked)} candidate(s) for {issue.issue_id} (scope {scope})",
                                  tuple(str(m.executor_id) for m in ranked), matches=ranked)
        return self._attempt(change)

    def executors_of_issue(self, issue_id):
        """The executors mapped to an issue, in the order they were mapped."""
        issue = self._require_issue(issue_id)
        found = (self.executors.get(e) for e in issue.executor_ids)
        return [e for e in found if e is not None]

    def executors_of_node(self, node_id):
        node = self.nodes.require(node_id)
        return [e for e in self.executors.all_executors() if e.node_id == node.node_id]

    # --- helpers -----------------------------------------------------------------------------------------------
    def _lineage(self, node_id):
        """The node, its ancestors and its descendants."""
        if self.hierarchy is None:
            raise DomainError("this needs the hierarchy (to find the ancestors and descendants of a node), but none was given")
        hierarchy = self.hierarchy()
        node = self.nodes.require(node_id)
        return {node.node_id} | {n.node_id for n in hierarchy.ancestors(node.node_id)} | {n.node_id for n in hierarchy.descendants(node.node_id)}

    def _require_issue(self, issue_id):
        issue = self.issues.get(as_issue_id(issue_id))
        if issue is None:
            raise DomainError(f"unknown issue {issue_id}")
        return issue

    def _require_executor(self, executor_id):
        executor = self.executors.get(as_executor_id(executor_id))
        if executor is None:
            raise DomainError(f"unknown executor {executor_id}")
        return executor

    def _attempt(self, change):
        try:
            return change()
        except (DomainError, ValueError) as error:
            return ExecutorResult(FAILED, str(error))
