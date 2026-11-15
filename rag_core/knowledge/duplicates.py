"""Duplicate and overlap detection (proposal section 7.7), built on word groups.

Three kinds of finding, from strongest to weakest:
- exact:   the two normalized texts are identical (same ContentHash).
- near:    almost the same words. Measured by RESEMBLANCE: of all the word groups in either text, the share found in both.
- overlap: a part of one text sits inside the other. The two texts share at least `min_shared_groups` word groups, which
           is about one or two copied sentences. The score reported is CONTAINMENT: of the word groups in the smaller
           text, the share found in the larger one. A ratio alone would miss a copied passage inside a long document,
           so the count decides and the ratio only describes.

A word group is the words in a row, for example 5 words. Words are lower-cased and punctuation is ignored, so a Markdown
file, its DOCX copy and a copy with different capital letters give the same groups.

What a finding is for: a person looks at it and decides. Nothing here merges or deletes knowledge (decision A13).
Versions of one item are never compared with each other: they are meant to be similar (decision A14).

Not built here: similarity by embeddings (needs the embedding model, Phase 8) and the final LLM check of unclear cases
(Phase 10). The policy's numbers are starting values, not tuned: see architecture/versioning_and_duplicates.md.
"""
import re
from dataclasses import dataclass
from enum import Enum

from ..shared.kernel import DomainError

TOKEN = re.compile(r"\w+")
COMPARED_METADATA = ("node_id", "title", "document_type", "field_of_activity", "confidentiality", "language")


class DuplicateKind(str, Enum):
    EXACT = "exact"
    NEAR = "near"
    OVERLAP = "overlap"


@dataclass(frozen=True)
class DuplicatePolicy:
    """Starting values, chosen from scripts/duplicate_experiment.py and not tuned: among the 190 pairs of different city
    documents the most shared word groups was 2 (size 5), and 2% of words replaced gives resemblance about 0.8."""
    word_group_size: int = 5
    near_limit: float = 0.8          # resemblance at or above this is a near duplicate
    min_shared_groups: int = 20      # sharing at least this many word groups is an overlap (20 groups = a 24-word passage)

    def __post_init__(self):
        if self.word_group_size < 1:
            raise DomainError("a word group has at least 1 word")
        if not 0 < self.near_limit <= 1:
            raise DomainError("near_limit must be above 0 and at most 1")
        if self.min_shared_groups < 1:
            raise DomainError("min_shared_groups is at least 1")

    def kind_for(self, resemblance_value, shared_groups):
        """The kind of a pair that is not exact: near, overlap, or None. Near is checked first."""
        if resemblance_value >= self.near_limit:
            return DuplicateKind.NEAR
        if shared_groups >= self.min_shared_groups:
            return DuplicateKind.OVERLAP
        return None


def words_of(text):
    return TOKEN.findall(text.lower())


def word_groups(text, size):
    """The set of word groups of a text. A text shorter than one group counts as a single group."""
    words = words_of(text)
    if not words:
        return frozenset()
    if len(words) < size:
        return frozenset({tuple(words)})
    return frozenset(tuple(words[i:i + size]) for i in range(len(words) - size + 1))


def resemblance(a, b):
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def containment(a, b):
    smaller = min(len(a), len(b))
    return len(a & b) / smaller if smaller else 0.0


@dataclass(frozen=True)
class DuplicateRecord:
    kind: DuplicateKind
    left_item: str
    left_tag: str
    right_item: str
    right_tag: str
    score: float                     # 1.0 for exact; resemblance for near; containment for overlap
    shared_groups: int
    same_node: bool
    metadata_differences: tuple = ()  # names of the compared metadata fields that differ

    @property
    def evidence(self):
        measure = {"exact": "same normalized text", "near": "resemblance", "overlap": "containment"}[self.kind.value]
        text = measure if self.kind == DuplicateKind.EXACT else f"{measure} {self.score:.3f}"
        text += f", {self.shared_groups} shared word groups, " + ("same node" if self.same_node else "different nodes")
        if self.metadata_differences:
            text += ", differs in " + " ".join(self.metadata_differences)
        return text


@dataclass(frozen=True)
class _Entry:
    item_id: str
    tag: str
    text_hash: str
    groups: frozenset
    metadata: dict


class DuplicateDetector:
    def __init__(self, policy=None):
        self.policy = policy or DuplicatePolicy()

    def _entry(self, item_id, version):
        return _Entry(str(item_id), str(version.tag), version.text_hash.hex,
                      word_groups(version.text, self.policy.word_group_size), version.metadata.as_dict())

    def _entries(self, items, all_versions):
        for item in items:
            for version in (item.versions if all_versions else (item.active_version,)):
                yield self._entry(item.item_id, version)

    def _compare(self, a, b):
        if a.item_id == b.item_id:
            return None                                   # versions of one item are never duplicates (A14)
        a, b = sorted((a, b), key=lambda e: (e.item_id, e.tag))
        shared = len(a.groups & b.groups)
        different = tuple(f for f in COMPARED_METADATA if a.metadata.get(f) != b.metadata.get(f))

        def record(kind, score):
            return DuplicateRecord(kind, a.item_id, a.tag, b.item_id, b.tag, round(score, 6), shared,
                                   a.metadata.get("node_id") == b.metadata.get("node_id"), different)

        if a.text_hash == b.text_hash:
            return record(DuplicateKind.EXACT, 1.0)
        near = resemblance(a.groups, b.groups)
        kind = self.policy.kind_for(near, shared)
        if kind == DuplicateKind.NEAR:
            return record(kind, near)
        if kind == DuplicateKind.OVERLAP:
            return record(kind, containment(a.groups, b.groups))
        return None

    def scan(self, items, all_versions=False):
        """Every finding among the items. By default only active versions are compared, because retrieval uses them."""
        entries = sorted(self._entries(list(items), all_versions), key=lambda e: (e.item_id, e.tag))
        found = []
        for i, a in enumerate(entries):
            for b in entries[i + 1:]:
                r = self._compare(a, b)
                if r is not None:
                    found.append(r)
        return found

    def check_new(self, item_id, version, items, all_versions=False):
        """Findings for one new version against the other items. Used by ingestion, before the version is saved."""
        new = self._entry(item_id, version)
        found = []
        for other in self._entries(list(items), all_versions):
            r = self._compare(new, other)
            if r is not None:
                found.append(r)
        return sorted(found, key=lambda r: (r.left_item, r.left_tag, r.right_item, r.right_tag))
