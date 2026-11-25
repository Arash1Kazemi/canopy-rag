"""The ingestion use case: register one file as a new knowledge item or a new version.

The steps follow the knowledge life cycle of the proposal (section 7.2):
register -> record metadata -> process the file -> extract the text -> chunk -> assign the version -> store.
Embedding and indexing come in Phase 8. An exact repeat of a version is always caught here, because it costs one
fingerprint comparison and keeps the same text from being indexed twice. When a detector is given, near duplicates and
overlaps with other items are added to the result as warnings: they never stop a registration, because a person decides.
A new version of an item also gets a change summary against the version registered before it.
"""
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..knowledge.changes import summarize_change
from ..knowledge.chunking import DEFAULT_POLICY, POLICIES, chunk_text
from ..knowledge.duplicates import DuplicateKind
from ..knowledge.metadata import MetadataRecord
from ..knowledge.model import ContentHash, KnowledgeItem, KnowledgeItemId, KnowledgeVersion, VersionTag
from ..shared.kernel import DomainError
from .formats import detect

NEW_ITEM, NEW_VERSION, SKIPPED_REPEAT, FAILED = "new item", "new version", "skipped: exact repeat", "failed"


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RegistrationRequest:
    path: Path
    item_id: str
    node_id: str
    version_tag: str
    title: str
    language: str = "en"
    document_type: str = "document"
    source_file: Optional[str] = None      # the name to record; defaults to the file name
    change_reason: str = ""
    extra_metadata: dict = field(default_factory=dict)
    notes: tuple = ()                      # said by the caller about this file; they become warnings of the result


@dataclass(frozen=True)
class IngestionResult:
    request: RegistrationRequest
    outcome: str
    chunks: int = 0
    active_tag: str = ""
    detail: str = ""
    warnings: tuple = ()


class IngestionService:
    def __init__(self, hierarchy, repository, extractors, policy=DEFAULT_POLICY, clock=utc_now, detector=None):
        self.hierarchy = hierarchy
        self.repo = repository
        self.extractors = extractors
        self.policy = POLICIES[policy] if isinstance(policy, str) else policy
        self.clock = clock
        self.detector = detector     # a DuplicateDetector, or None to skip near and overlap checks

    def register(self, request):
        """Never raises for a bad file: the result says what went wrong, so one bad file does not stop a batch."""
        try:
            return self._register(request)
        except DomainError as error:
            return IngestionResult(request, FAILED, detail=str(error))

    def _register(self, req):
        node = self.hierarchy.node(req.node_id)                       # an unknown node is an error
        item_id, tag = KnowledgeItemId(req.item_id), VersionTag(req.version_tag)
        path = Path(req.path)
        data = path.read_bytes()
        fmt = detect(path)
        doc = self.extractors.extract(path, fmt)
        if not doc.text.strip():
            raise DomainError(f"{path.name} gave no text")
        text_hash = ContentHash.of_text(doc.text)

        item = self.repo.get(str(item_id))
        if item is not None:
            if item.node_id != str(node.node_id):
                raise DomainError(f"item {item_id} belongs to node {item.node_id}, not {node.node_id}")
            same = item.version_with_text(text_hash)
            if same is not None:
                return IngestionResult(req, SKIPPED_REPEAT, active_tag=str(item.active_tag),
                                       detail=f"same text as {item_id} version {same.tag} ({same.metadata['source_file']})")
            if item.version(tag) is not None:
                raise DomainError(f"H04: {item_id} version {tag} exists with different text; give the new text a new version tag")
        elif node.is_terminal and self.repo.items_of_node(str(node.node_id)):
            raise DomainError(f"H10: {node.node_id} is a terminal node and already has its one summary document")

        source_file = req.source_file or path.name
        metadata = MetadataRecord({
            "node_id": str(node.node_id), "title": req.title, "document_type": req.document_type,
            "field_of_activity": node.field_of_activity, "confidentiality": node.confidentiality.value,
            "language": req.language, "source_file": source_file, "file_format": fmt.value,
            "file_sha256": ContentHash.of_bytes(data).hex, "text_sha256": text_hash.hex,
            "extraction_method": doc.method, "page_count": doc.page_count, "ingested_at": self.clock(),
            "change_reason": req.change_reason, **req.extra_metadata,
        })
        chunks = chunk_text(doc.text, doc.sections, self.policy, item_id=item_id, version_tag=tag,
                            node_id=str(node.node_id), source_file=source_file)
        change = summarize_change(item.versions[-1].text, doc.text) if item is not None else ""
        version = KnowledgeVersion(tag, doc.text, metadata, chunks, diff_summary=change)

        warnings = list(req.notes) + list(doc.warnings)
        for other, other_version in self.repo.find_by_text(text_hash):
            if other.item_id != item_id:
                warnings.append(f"same text as {other.item_id} version {other_version.tag}")
        if self.detector is not None:
            for found in self.detector.check_new(item_id, version, self.repo.all_items()):
                if found.kind == DuplicateKind.EXACT:      # an exact repeat in another item is noted above
                    continue
                if found.left_item == str(item_id):
                    other_id, other_tag = found.right_item, found.right_tag
                else:
                    other_id, other_tag = found.left_item, found.left_tag
                lead = "near duplicate of" if found.kind == DuplicateKind.NEAR else "overlaps with"
                warnings.append(f"{lead} {other_id} version {other_tag}: {found.evidence}")

        if item is None:
            item, outcome = KnowledgeItem.register(item_id, str(node.node_id), version), NEW_ITEM
        else:
            item.add_version(version, activate=item.is_newer_than_active(tag))
            outcome = NEW_VERSION
        self.repo.save(item)
        return IngestionResult(req, outcome, chunks=len(chunks), active_tag=str(item.active_tag), warnings=tuple(warnings),
                               detail="" if item.active_tag == tag else f"kept {item.active_tag} active (it is newer)")
