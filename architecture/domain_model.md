# Domain model specification

Project: offline hierarchical RAG core. Source: Phase 3 of the project proposal (sections 5.2, 5.3, 6, 7, 12 to 16). Status: draft for supervisor review. Date: 2026-11-01.

This is the second Phase 3 deliverable. It lists every entity, value object and aggregate: its fields, the rules it guards, and the events it records. Every name is in `glossary/glossary.md`. The contexts built so far have code in `rag_core/`; the others are specified here and built in their phase.

How to read it: an **entity** has an identity that stays the same while its data changes. A **value object** is only its value: two with the same value are the same, and it never changes. An **aggregate** is a group of objects changed only through its root, so the root can guard the group's rules.

## Shared kernel (`rag_core/shared/kernel.py`)

| Name | Kind | Values | Used by |
| --- | --- | --- | --- |
| Confidentiality | value | internal, confidential | nodes, metadata |
| TransferDetailLevel | value | executive, managerial, technical_summary, detailed_technical (rank 1 to 4) | a node's reporting format, transfer packages |
| TransferRule | value | detail level, minimum judge score, required and excluded topics, required fields, output format, maximum words, citation level; only the detail level is required, an empty field means not decided | the layer registry (Phase 6), transfer packages (Phase 11) |
| DomainError | error | its message names the rule that was broken, such as "H03: ..." | everything |
| DomainEvent | value | a name and details | aggregates |

## Organizational Hierarchy (`rag_core/organization/model.py`), built

**Aggregate: Hierarchy** (root). One per organization.

| Member | Kind | Fields |
| --- | --- | --- |
| Hierarchy | entity, root | its nodes, in the order they were added; its layer registry; `events` |
| Node | entity | `node_id`, `name`, `layer`, `parent_id`, `field_of_activity`, `is_terminal`, `reporting_format`, `min_judge_score`, `confidentiality` |
| Layer | entity | `index`, `node_ids` (derived from the nodes), `name`, `role`, `rule` (a TransferRule, or none when the layer receives nothing) |
| NodeIdentifier | value | text of letters, digits, `_`, `-` |
| LayerIndex | value | a whole number from 0 |

Rules:

1. A node id is never reused.
2. H02: exactly one root, in layer 0; every other node is one layer below its parent.
3. A parent is added before its child.
4. H10 (first half): a terminal node has no children.
5. A node's layer follows from its parent (H02), also after a move: the node and everything under it shift together.
6. A node cannot move if it is the root, or if the new parent is the node itself, one of its descendants, a terminal node, or a layer that has no transfer rule (once a layer registry exists).
7. A node's reporting format and minimum judge score are the rule of its parent's layer. They are re-derived when the node moves or the rule changes (decision A16).
8. A layer is defined once. A layer's rule may not ask for more detail than the layer below it.
9. A terminal node has no children and one summary document (H10), also when a node becomes terminal later.

Questions: `ancestors`, `descendants`, `siblings`, `nodes_in_layer`, `terminal_nodes`, `layer_definition`, `receiving_rule`, `problems`. Changes: `add_node`, `move_node`, `set_terminal`, `change_details`, `define_layer`, `set_layer_rule`. Events: `NodeAdded`, `NodeMoved`, `NodeTerminalChanged`, `NodeDetailsChanged`, `LayerDefined`, `LayerRuleChanged`.

**Use cases** (`rag_core/workflows/organization.py`, Phase 6): `OrganizationService` defines a node, moves a node, makes a node terminal, changes a node, defines a layer and sets a layer's rule. Each saves only if every rule held. The document half of H10 is checked here because it needs the knowledge repository. Details are in `architecture/hierarchy_and_layers.md`.

Questions it answers: `node`, `children`, `parent`, `path` (root down to a node), `layers`. Event: `NodeAdded`.

## Knowledge Management (`rag_core/knowledge/`), built

**Aggregate: KnowledgeItem** (root). One per controlled source of knowledge, such as a document.

| Member | Kind | Fields |
| --- | --- | --- |
| KnowledgeItem | entity, root | `item_id`, `node_id`, versions, active tag, `events` |
| KnowledgeVersion | entity | `tag`, `text`, `metadata`, `chunks`, `sequence`, `previous_tag`, `diff_summary` |
| KnowledgeChunk | entity | `chunk_id` (item@version#order), `node_id`, `order`, `text`, `location` |
| KnowledgeItemId | value | text, such as D10 |
| VersionTag | value | text, such as 2; ordered naturally (2 before 10) |
| ContentHash | value | 64 hex characters (SHA-256) of bytes or of normalized text |
| MetadataRecord | value | named text fields checked against the schema in `architecture/metadata_fields.csv` |
| KnowledgeScope | value | `field_of_activity`, `confidentiality`, `usage` (default `own_node`) |
| SourceLocation | value | item, version, file, character span, pages, heading path |
| DocumentFormat | value | md, txt, docx, doc, pdf |
| ChunkStage | value | created, embedded, checked, indexed (Phase 5) |
| DuplicateRecord | value | kind (exact, near, overlap), the two versions, score, shared word groups, same node, metadata differences (Phase 5) |
| DuplicatePolicy | value | word group size, near limit, minimum shared groups (Phase 5) |
| ChunkingPolicy | value | name, words per chunk, overlap, whether chunks stay inside sections |

Rules:

1. H03: exactly one version is active, and it is one of the item's versions.
2. H04: a version tag is never reused for new text, and there is no way to remove a version.
3. An item belongs to one node; each version's metadata names that node, and each chunk carries it.
4. A version is complete when it is made (text, metadata, chunks) and never changes after.
5. A newer version becomes active when it is added; an older one added late stays inactive (decision A4 in `architecture/architecture.md`).
6. Metadata has every required field, no unknown field, and every value passes its rule.

Questions it answers: `active_version`, `version(tag)`, `version_with_text(hash)` (an exact repeat), `scope`. Events: `KnowledgeVersionAdded`, `ActiveVersionChanged`.

**Domain service: chunking** (`knowledge/chunking.py`). Cuts a version's text into chunks under a ChunkingPolicy. The rules are in `architecture/chunking_spec.md`.

**Repository:** `KnowledgeRepository` with `get`, `save`, `all_items`, `items_of_node`, `find_by_text`, `active_chunks(node_id)`.

**Use case: ingestion** (`rag_core/ingestion/service.py`). Registers a file as a new item or version. It also checks the second half of H10 (one summary document per terminal node), because that rule spans several items. The flow is in `architecture/ingestion.md`.

**Built in Phase 5** (details in `architecture/versioning_and_duplicates.md`):

- **Change summary** (`knowledge/changes.py`): a note of what changed between a version and the one registered before it, stored in `diff_summary`.
- **Chunk life cycle** (`knowledge/lifecycle.py`): `ChunkLifecycle` moves a chunk through the stages one step at a time. A chunk is retrievable only if it is indexed and its version is active.
- **Duplicate detection** (`knowledge/duplicates.py`): `DuplicateDetector` finds exact, near and overlap pairs among different items and gives a `DuplicateRecord` for each. Versions of one item are never compared. A record is advice for a person; nothing is merged or deleted.

## RAG Core (`rag_core/rag/`), citation model built

| Name | Kind | Fields |
| --- | --- | --- |
| Citation | value | `source_stem`, `chunk_id`, `page_start`, `page_end`, `heading_path` |
| RetrievalQuery | value (Phase 8) | normalized question text, the asking node, k |
| SimilarityScore | value (Phase 8) | a number; higher is closer |

Rules: an answer cites file stems in square brackets or says "insufficient knowledge" (H09); retrieval for a node returns only that node's active chunks (H01). The citation rules are in `architecture/citation_model.md`.

## Issue Management, planned (Phase 7)

**Aggregate: Issue** (root), with its SubIssues inside it.

| Member | Kind | Fields |
| --- | --- | --- |
| Issue | entity, root | id, node, type (problem, question, need, research gap, operational concern), title, description, metadata, status, sub-issues, relative position |
| SubIssue | entity | id, parent issue, title, status, progress |
| ProgressPercentage | value | a whole number from 0 to 100 |

Rules to own: a sub-issue stays in its parent's node; H07 (status and progress follow fixed rules: the same input gives the same result). The issue data of the city is in `case_study/issues.csv`.

## Executor Management, planned (Phase 9)

**Aggregate: Executor** (root): id, kind (person, team, unit, capability), node, expertise fields, availability. Rule to own: matching an executor to an issue is deterministic for the same inputs.

## Issue-Knowledge-Executor, planned (Phase 9)

The IKE model: typed relations such as "issue depends on knowledge" and "executor can solve issue". Each relation names two ids and a type. Rule to own: both ends of a relation exist and live in the same node, unless the relation type allows crossing (decided in Phase 9).

## Knowledge Transfer, planned (Phase 11)

**Aggregate: TransferPackage** (root): id, source node, target node (the parent), cycle, detail level (TransferDetailLevel), content with citations, judge score, status (draft, held, sent).

Rules to own: the target is the source node's parent; the detail level is the target's reporting format; H05 (a package scoring below the target's JudgeThreshold is never sent). The Cycle uses the `ActiveVersionChanged` events to find what changed.

## Evaluation and Judging, planned (Phase 10)

| Name | Kind | Fields |
| --- | --- | --- |
| JudgeScore | entity | id, what was judged, rubric, points per criterion, total, pass or fail, explanation |
| JudgeRubric | value | criteria and their points, 20 in total |
| JudgeThreshold | value | the pass mark, 18 out of 20 by default |

Rules to own: the points add up to the total; the total is at most the rubric's maximum; pass means total at or above the threshold.

## RFP and Proposal Management, planned (Phase 13)

**Aggregates:** RFP (root: id, issue, node, required sections, criteria), Proposal (an RFP response: id, RFP, author, content), FeedbackReport (strengths, weaknesses, missing requirements, recommendation; each critique points to an RFP criterion).

Rules to own: a draft RFP has every required section; every critique in a FeedbackReport names an RFP criterion.

## Model and Prompt Management (`rag_core/models/ports.py`), ports built

| Port | Method | Adapter now |
| --- | --- | --- |
| EmbeddingModel | `embed(texts)` | none in the core yet (Phase 2 runner) |
| LanguageModel | `generate(prompt)` | none in the core yet (Phase 2 runner) |
| VisionModel | `read_page(png)` | `OllamaVisionModel` with glm-ocr |

The model registry (`models/model_registry.csv`) and the prompt templates (`prompts/`) stay as Phase 2 made them.
