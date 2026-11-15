"""The knowledge model: KnowledgeItem (the aggregate root), KnowledgeVersion, KnowledgeChunk and their value objects.

The rules this file guards:
- H03: an item has exactly one active version.
- H04: an update adds a version and never deletes or overwrites an old one. There is no remove method on purpose.
- An item belongs to one node, and every version of it says so in its metadata.
"""
import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..shared.kernel import Confidentiality, DomainError, DomainEvent
from .metadata import MetadataRecord

ID_PATTERN = re.compile(r"[A-Za-z0-9_\-]+")
TAG_PATTERN = re.compile(r"[A-Za-z0-9._\-]+")


@dataclass(frozen=True)
class KnowledgeItemId:
    """The stable id of a knowledge item, such as D10."""
    value: str

    def __post_init__(self):
        if not ID_PATTERN.fullmatch(self.value or ""):
            raise DomainError(f"a knowledge item id uses letters, digits, '_' or '-', not {self.value!r}")

    def __str__(self):
        return self.value


@dataclass(frozen=True)
class VersionTag:
    """The unchangeable id of a version, such as 2 or v2."""
    value: str

    def __post_init__(self):
        if not TAG_PATTERN.fullmatch(self.value or ""):
            raise DomainError(f"a version tag uses letters, digits, '.', '_' or '-', not {self.value!r}")

    def __str__(self):
        return self.value

    def sort_key(self):
        """Natural order: 2 < 10, and v2 < v10. Used to decide which version is newer."""
        return [(0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", self.value.lower()) if p]


def normalize_text(text):
    """The text form used for ContentHash: whitespace runs become one space, and the ends are trimmed.
    Case is kept, because '120 buses' and '120 Buses' are the same but 'US' and 'us' may not be."""
    return " ".join(text.split())


@dataclass(frozen=True)
class ContentHash:
    """A SHA-256 fingerprint. Equal fingerprints mean equal content."""
    hex: str

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{64}", self.hex or ""):
            raise DomainError(f"a content hash is 64 lowercase hex characters, not {self.hex!r}")

    @classmethod
    def of_bytes(cls, data):
        return cls(hashlib.sha256(data).hexdigest())

    @classmethod
    def of_text(cls, text):
        return cls(hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest())

    def __str__(self):
        return self.hex


class DocumentFormat(str, Enum):
    MARKDOWN = "md"
    PLAIN_TEXT = "txt"
    DOCX = "docx"
    DOC = "doc"
    PDF = "pdf"


@dataclass(frozen=True)
class KnowledgeScope:
    """Field of activity, confidentiality and allowed use. Read from a version's metadata."""
    field_of_activity: str
    confidentiality: Confidentiality
    usage: str = "own_node"  # H01: by default an item answers questions only in its own node

    @classmethod
    def of(cls, metadata):
        return cls(metadata["field_of_activity"], Confidentiality(metadata["confidentiality"]))


@dataclass(frozen=True)
class SourceLocation:
    """Where a chunk comes from. Pages are 1-based and None when the format has no pages."""
    item_id: KnowledgeItemId
    version_tag: VersionTag
    source_file: str
    char_start: int
    char_end: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    heading_path: tuple = ()

    def __post_init__(self):
        if not 0 <= self.char_start < self.char_end:
            raise DomainError(f"a source location needs 0 <= start < end, not {self.char_start}..{self.char_end}")
        if (self.page_start is None) != (self.page_end is None):
            raise DomainError("a source location has both page_start and page_end, or neither")
        if self.page_start is not None and not 1 <= self.page_start <= self.page_end:
            raise DomainError(f"pages must satisfy 1 <= start <= end, not {self.page_start}..{self.page_end}")

    @property
    def source_stem(self):
        """The file name without folder and extension: D10_bus_fleet_inventory_v2. Answers cite it."""
        name = self.source_file.replace("\\", "/").rsplit("/", 1)[-1]
        return name.rsplit(".", 1)[0] if "." in name else name


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str        # item@version#order, for example D10@2#3
    node_id: str
    order: int           # 1, 2, 3 ... inside the version
    text: str
    location: SourceLocation

    def __post_init__(self):
        if self.order < 1:
            raise DomainError("chunk order starts at 1")
        if not self.text.strip():
            raise DomainError(f"chunk {self.chunk_id} is empty")

    @staticmethod
    def make_id(item_id, version_tag, order):
        return f"{item_id}@{version_tag}#{order}"


@dataclass(frozen=True)
class KnowledgeVersion:
    """One version of an item. It is complete when it is created: text, metadata and chunks, so it never changes."""
    tag: VersionTag
    text: str
    metadata: MetadataRecord
    chunks: tuple
    sequence: int = 0                      # set by the item: 1 for the first version registered, then 2, 3 ...
    previous_tag: Optional[VersionTag] = None
    diff_summary: str = ""

    def __post_init__(self):
        if not self.text.strip():
            raise DomainError(f"version {self.tag} has no text")
        for c in self.chunks:
            if c.location.version_tag != self.tag:
                raise DomainError(f"chunk {c.chunk_id} belongs to version {c.location.version_tag}, not {self.tag}")

    @property
    def text_hash(self):
        return ContentHash(self.metadata["text_sha256"])


class KnowledgeItem:
    """The aggregate root of Knowledge Management. Change versions only through these methods."""

    def __init__(self, item_id, node_id, versions=(), active_tag=None):
        self.item_id = item_id if isinstance(item_id, KnowledgeItemId) else KnowledgeItemId(item_id)
        self.node_id = str(node_id)
        self._versions = list(versions)
        self._active = active_tag
        self.events = []
        if self._versions and self._active not in {v.tag for v in self._versions}:
            raise DomainError(f"H03: item {self.item_id} must have exactly one active version")

    @classmethod
    def register(cls, item_id, node_id, first_version):
        item = cls(item_id, node_id)
        item.add_version(first_version, activate=True)
        return item

    # --- changes
    def add_version(self, version, activate=True):
        if version.metadata["node_id"] != self.node_id:
            raise DomainError(f"item {self.item_id} belongs to node {self.node_id}; "
                              f"a version cannot say node {version.metadata['node_id']}")
        if any(v.tag == version.tag for v in self._versions):
            raise DomainError(f"H04: item {self.item_id} already has version {version.tag}; a version is never overwritten")
        for c in version.chunks:
            if c.location.item_id != self.item_id or c.node_id != self.node_id:
                raise DomainError(f"chunk {c.chunk_id} does not belong to item {self.item_id} in node {self.node_id}")
        stored = KnowledgeVersion(version.tag, version.text, version.metadata, version.chunks,
                                  sequence=len(self._versions) + 1,
                                  previous_tag=self._versions[-1].tag if self._versions else None,
                                  diff_summary=version.diff_summary)
        self._versions.append(stored)
        self.events.append(DomainEvent("KnowledgeVersionAdded", (("item_id", str(self.item_id)), ("tag", str(stored.tag)))))
        if activate or self._active is None:   # the first version is always active (H03)
            self.activate(stored.tag)
        return stored

    def activate(self, tag):
        tag = tag if isinstance(tag, VersionTag) else VersionTag(str(tag))
        if not any(v.tag == tag for v in self._versions):
            raise DomainError(f"item {self.item_id} has no version {tag}")
        if tag != self._active:
            self._active = tag
            self.events.append(DomainEvent("ActiveVersionChanged", (("item_id", str(self.item_id)), ("tag", str(tag)))))

    # --- questions
    @property
    def versions(self):
        return tuple(self._versions)

    @property
    def active_tag(self):
        return self._active

    @property
    def active_version(self):
        return next(v for v in self._versions if v.tag == self._active)

    def version(self, tag):
        tag = tag if isinstance(tag, VersionTag) else VersionTag(str(tag))
        return next((v for v in self._versions if v.tag == tag), None)

    def version_with_text(self, text_hash):
        """The version whose normalized text has this fingerprint, if any: an exact repeat."""
        return next((v for v in self._versions if v.text_hash == text_hash), None)

    def is_newer_than_active(self, tag):
        return self._active is None or tag.sort_key() > self._active.sort_key()

    @property
    def scope(self):
        return KnowledgeScope.of(self.active_version.metadata)
