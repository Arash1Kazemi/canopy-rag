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
