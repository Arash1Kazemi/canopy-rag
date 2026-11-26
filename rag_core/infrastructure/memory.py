"""In-memory repositories: for unit tests and quick runs. Nothing is written to disk."""
import copy

from ..knowledge.model import KnowledgeItem


class InMemoryKnowledgeRepository:
    def __init__(self):
        self._items = {}

    def get(self, item_id):
        stored = self._items.get(str(item_id))
        return None if stored is None else self._rebuild(stored)

    def save(self, item):
        old = self._items.get(str(item.item_id))
        if old is not None:
            for v in old.versions:  # H04 at the storage level too: a stored version stays as it was
                new = item.version(v.tag)
                if new is None or new.text != v.text or new.metadata != v.metadata:
                    raise ValueError(f"H04: version {v.tag} of {item.item_id} cannot be removed or changed")
        self._items[str(item.item_id)] = self._rebuild(item)

    @staticmethod
    def _rebuild(item):
        # a fresh object each time, so a caller cannot change what is stored without calling save
        return KnowledgeItem(item.item_id, item.node_id, copy.copy(list(item.versions)), item.active_tag)

    def all_items(self):
        return [self.get(k) for k in self._items]

    def items_of_node(self, node_id):
        return [i for i in self.all_items() if i.node_id == str(node_id)]

    def find_by_text(self, text_hash):
        return [(i, v) for i in self.all_items() for v in i.versions if v.text_hash == text_hash]

    def active_chunks(self, node_id=None):
        items = self.all_items() if node_id is None else self.items_of_node(node_id)
        return [c for i in items for c in i.active_version.chunks]


class InMemoryHierarchyRepository:
    """Like a real store: `load` gives a copy, so a change that fails halfway cannot alter what is stored."""

    def __init__(self, hierarchy):
        self._hierarchy = copy.deepcopy(hierarchy)

    def load(self):
        return copy.deepcopy(self._hierarchy)

    def save(self, hierarchy):
        self._hierarchy = copy.deepcopy(hierarchy)


class InMemoryIssueRepository:
    """Issues in a dict. An Issue is frozen, so storing the object itself is safe. `add_all` checks every id before it
    stores anything, so a group is stored whole or not at all, like the SQLite transaction."""

    def __init__(self, issues=()):
        self._issues = {}
        self.add_all(issues)

    def get(self, issue_id):
        return self._issues.get(str(issue_id))

    def all_issues(self):
        return list(self._issues.values())

    def is_empty(self):
        return not self._issues

    def add_all(self, issues):
        issues = list(issues)
        ids = [str(i.issue_id) for i in issues]
        if len(set(ids)) != len(ids):
            raise ValueError("the same issue id appears twice in one group")
        stored = [i for i in ids if i in self._issues]
        if stored:
            raise ValueError(f"issue id already stored: {', '.join(stored)}")
        missing = [str(i.parent_issue_id) for i in issues
                   if i.parent_issue_id is not None and str(i.parent_issue_id) not in self._issues and str(i.parent_issue_id) not in ids]
        if missing:   # the same refusal as the SQLite foreign key
            raise ValueError(f"unknown parent issue: {', '.join(missing)}")
        for issue in issues:
            self._issues[str(issue.issue_id)] = issue

    def update(self, issue):
        if str(issue.issue_id) not in self._issues:
            raise ValueError(f"issue {issue.issue_id} is not stored, so it cannot be updated")
        self._issues[str(issue.issue_id)] = issue
