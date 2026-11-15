"""Small builders for core tests, so each test sets up only what it is about."""
from rag_core.knowledge.chunking import POLICIES, chunk_text
from rag_core.knowledge.metadata import MetadataRecord
from rag_core.knowledge.model import ContentHash, KnowledgeItemId, KnowledgeVersion, VersionTag
from rag_core.organization.model import Hierarchy, LayerIndex, Node, NodeIdentifier
from rag_core.shared.kernel import TransferDetailLevel, TransferRule


def node(node_id, layer, parent=None, terminal=False, field="transport", reporting=None, score=None):
    return Node(NodeIdentifier(node_id), f"Node {node_id}", LayerIndex(layer),
                NodeIdentifier(parent) if parent else None, field, is_terminal=terminal,
                reporting_format=TransferDetailLevel(reporting) if reporting else None, min_judge_score=score)


def rule(level, score=18, **fields):
    return TransferRule(TransferDetailLevel(level), min_judge_score=score, **fields)


def layered_hierarchy():
    """The City's shape with a layer registry: N0 > N1, N2, N3 (terminal) > N4 (under N1) > N6. Every node sends what the
    rule of its parent's layer asks for."""
    h = Hierarchy()
    h.define_layer(0, "Strategic layer", rule=rule("executive"))
    h.define_layer(1, "Parent organizations", rule=rule("managerial"))
    h.define_layer(2, "Units", rule=rule("technical_summary"))
    h.define_layer(3, "Projects")
    h.add_node(node("N0", 0))
    h.add_node(node("N1", 1, "N0", reporting="executive", score=18))
    h.add_node(node("N2", 1, "N0", reporting="executive", score=18))
    h.add_node(node("N3", 1, "N0", terminal=True, field="housing", reporting="executive", score=18))
    h.add_node(node("N4", 2, "N1", reporting="managerial", score=18))
    h.add_node(node("N6", 3, "N4", reporting="technical_summary", score=18))
    return h


def small_hierarchy():
    """N0 at the top; N1 under it; N3 a terminal node under N0."""
    h = Hierarchy()
    h.add_node(node("N0", 0))
    h.add_node(node("N1", 1, "N0"))
    h.add_node(node("N3", 1, "N0", terminal=True, field="housing"))
    return h


def metadata(node_id="N1", text="some text", **changes):
    values = {"node_id": node_id, "title": "A title", "document_type": "document", "field_of_activity": "transport",
              "confidentiality": "internal", "language": "en", "source_file": "D90_test.md", "file_format": "md",
              "file_sha256": "0" * 64, "text_sha256": ContentHash.of_text(text).hex, "extraction_method": "markdown",
              "ingested_at": "2026-11-01T10:00:00Z"}
    values.update(changes)
    return MetadataRecord(values)


def version(tag="1", text="The fleet has 135 buses.", item="D90", node_id="N1", source_file="D90_test.md"):
    chunks = chunk_text(text, (), POLICIES["words80"], item_id=KnowledgeItemId(item), version_tag=VersionTag(tag),
                        node_id=node_id, source_file=source_file)
    return KnowledgeVersion(VersionTag(tag), text, metadata(node_id, text, source_file=source_file), chunks)
