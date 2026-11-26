"""The issue workflows (Phase 7, proposal section 12): create an issue, change its status, add a "blocked by" link,
compare a draft, suggest sub-issues and save the accepted ones, and read progress and relative position.

Like the node workflows, a change never raises for a broken rule: the result says what went wrong and nothing is
saved. Every workflow gets its repository, node directory, clock and progress weights as arguments, and the language
model as an argument of the one workflow that needs it, so unit tests pass test doubles and need no running model.
"""
from dataclasses import dataclass

from ..issues.comparison import IssueDraft, compare_draft
from ..issues.model import Issue, as_issue_id
from ..issues.progress import compute_progress
from ..issues.rules import check_issues, next_issue_id, next_position, relative_position
from ..issues.suggestions import fill_prompt, parse_suggestions
from ..shared.kernel import DomainError

ISSUE_CREATED, STATUS_CHANGED, BLOCKER_ADDED = "issue created", "status changed", "blocker added"
COMPARED, SUGGESTED, SUB_ISSUES_SAVED, FAILED = "compared", "suggested", "sub-issues saved", "failed"
SUGGESTION_SOURCE = "sub-issue suggestion (prompt suggest_sub_issues_v1)"


@dataclass(frozen=True)
class IssueResult:
    outcome: str
    detail: str = ""
    issue_ids: tuple = ()
    matches: tuple = ()
    suggestions: tuple = ()

    @property
    def ok(self):
        return self.outcome != FAILED


class IssueService:
    def __init__(self, repository, nodes, clock, weights):
        """`repository` is an IssueRepository, `nodes` a NodeDirectory, `clock()` gives the time as ISO text, and
        `weights` are the ProgressWeights (from config/issue_progress_weights.csv)."""
        self.repo = repository
        self.nodes = nodes
        self.clock = clock
        self.weights = weights

    # --- changes -----------------------------------------------------------------------------------------------
    def create_issue(self, node_id, title, description, *, parent_id=None, issue_type="problem", priority="not_set",
                     category="", field_of_activity=None, metadata=None, blocked_by=(), position=None):
        """12.1: an issue with its metadata. A sub-issue gets its parent's node; the field of activity defaults to the node's."""
        def change(existing):
            node = self.nodes.require(node_id)
            parent = as_issue_id(parent_id) if parent_id else None
            issue = Issue(
                issue_id=next_issue_id(existing), node_id=node.node_id, parent_issue_id=parent, title=title,
                description=description, issue_type=issue_type, priority=priority, category=category,
                field_of_activity=field_of_activity or node.field_of_activity, created_at=self.clock(),
                position=position or next_position(parent, node.node_id, existing), metadata=metadata or {},
                blocked_by=tuple(blocked_by))
            check_issues([issue], existing, self.nodes)
            self.repo.add_all([issue])
            kind = f"sub-issue of {parent}" if parent else "issue"
            return IssueResult(ISSUE_CREATED, f"{issue.issue_id} is a new {kind} in {issue.node_id} at position {issue.position}",
                               (str(issue.issue_id),))
        return self._attempt(change)

    def set_status(self, issue_id, status):
        """H07: only an allowed move is saved."""
        def change(existing):
            issue = self._require(issue_id)
            changed = issue.with_status(status)
            self.repo.update(changed)
            return IssueResult(STATUS_CHANGED, f"{issue.issue_id}: {issue.status.value} -> {changed.status.value}", (str(issue.issue_id),))
        return self._attempt(change)

    def add_blocker(self, issue_id, blocker_id):
        """Record that one issue waits on another of the same node. A link that closes a cycle is refused."""
        def change(existing):
            changed = self._require(issue_id).with_blocker(blocker_id)
            check_issues([changed], existing, self.nodes)
            self.repo.update(changed)
            return IssueResult(BLOCKER_ADDED, f"{changed.issue_id} is now blocked by {as_issue_id(blocker_id)}", (str(changed.issue_id),))
        return self._attempt(change)

    def suggest_sub_issues(self, issue_id, model, prompt_template):
        """12.1 step 7: ask the language model for sub-issues. Nothing is saved: a person decides first."""
        def change(existing):
            issue = self._require(issue_id)
            prompt = fill_prompt(prompt_template, title=issue.title, description=issue.description,
                                 field_of_activity=issue.field_of_activity)
            try:
                reply = model.generate(prompt)
            except Exception as error:      # any failure of the model (not reachable, timeout) is reported, not raised
                return IssueResult(FAILED, f"the language model could not answer: {error}. Is Ollama running on "
                                           f"127.0.0.1:11500? See docs/operator_guide.md")
            suggestions = tuple(parse_suggestions(reply))
            if not suggestions:
                return IssueResult(FAILED, "the model's reply held no suggestion in the form 'title | description'")
            return IssueResult(SUGGESTED, f"{len(suggestions)} suggestion(s) for {issue.issue_id}; nothing is saved until "
                                          f"a person accepts them", (str(issue.issue_id),), suggestions=suggestions)
        return self._attempt(change)

    def accept_sub_issues(self, parent_id, chosen):
        """Save the suggestions a person accepted (as they were, or edited) as sub-issues, all in one transaction.
        A rejected suggestion is simply not in `chosen`. If one fails, none is saved."""
        def change(existing):
            parent = self._require(parent_id)
            if not chosen:
                raise DomainError("no suggestion was accepted, so nothing is saved")
            new, so_far = [], list(existing)
            for suggestion in chosen:
                issue = Issue(
                    issue_id=next_issue_id(so_far), node_id=parent.node_id, parent_issue_id=parent.issue_id,
                    title=suggestion.title, description=suggestion.description, issue_type=parent.issue_type,
                    category=parent.category, field_of_activity=parent.field_of_activity, created_at=self.clock(),
                    position=next_position(parent.issue_id, parent.node_id, so_far),
                    metadata={"source": SUGGESTION_SOURCE})
                new.append(issue)
                so_far.append(issue)
            check_issues(new, existing, self.nodes)
            self.repo.add_all(new)
            ids = tuple(str(i.issue_id) for i in new)
            return IssueResult(SUB_ISSUES_SAVED, f"{len(ids)} sub-issue(s) of {parent.issue_id} saved together: {', '.join(ids)}", ids)
        return self._attempt(change)

    # --- questions ---------------------------------------------------------------------------------------------
    def compare(self, node_id, title, description="", similarity=None):
        """12.1 steps 3 and 4: rank the issues of the same node by how much they resemble a draft."""
        def change(existing):
            node = self.nodes.require(node_id)
            matches = tuple(compare_draft(IssueDraft(node.node_id, title, description), existing, similarity))
            return IssueResult(COMPARED, f"{len(matches)} candidate(s) in {node.node_id}", matches=matches)
        return self._attempt(change)

    def progress(self, issue_id):
        issue = self._require(issue_id)
        return compute_progress(issue, self.sub_issues(issue_id), self.weights)

    def sub_issues(self, issue_id):
        key = as_issue_id(issue_id)
        return [i for i in self.repo.all_issues() if i.parent_issue_id == key]

    def position(self, issue_id):
        return relative_position(issue_id, self.repo.all_issues())

    def issues_of_node(self, node_id):
        node = self.nodes.require(node_id)
        return [i for i in self.repo.all_issues() if i.node_id == node.node_id]

    # --- helpers -----------------------------------------------------------------------------------------------
    def _require(self, issue_id):
        issue = self.repo.get(as_issue_id(issue_id))
        if issue is None:
            raise DomainError(f"unknown issue {issue_id}")
        return issue

    def _attempt(self, change):
        try:
            return change(self.repo.all_issues())
        except (DomainError, ValueError) as error:
            return IssueResult(FAILED, str(error))
