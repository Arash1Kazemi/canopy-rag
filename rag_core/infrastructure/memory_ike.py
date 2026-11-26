"""The in-memory IKE repository: for unit tests and quick runs. Nothing is written to disk."""
from ..ike.model import sorted_relations


class InMemoryIkeRepository:
    def __init__(self):
        self._relations = {}

    def add_all(self, relations):
        relations = list(relations)
        keys = [r.edge_key for r in relations]
        if len(set(keys)) != len(keys):
            raise ValueError("the same relation appears twice in one group, so nothing was saved")
        known = [r for r in relations if r.edge_key in self._relations]
        if known:
            raise ValueError(f"relation already stored, so nothing was saved: {_label(known[0])}")
        for relation in relations:
            self._relations[relation.edge_key] = relation

    def all_relations(self):
        return sorted_relations(self._relations.values())

    def relations_of_node(self, node_id):
        return [r for r in self.all_relations() if str(r.node_id) == str(node_id)]

    def contains(self, relation):
        return relation.edge_key in self._relations

    def is_empty(self):
        return not self._relations


def _label(relation):
    return f"{relation.source} {relation.relation_type.value} {relation.target}"
