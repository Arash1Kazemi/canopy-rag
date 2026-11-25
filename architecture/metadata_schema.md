# Metadata schema

Project: offline hierarchical RAG core. Source: Phase 4 of the project proposal (sections 7.3 to 7.7). Status: draft for supervisor review. Date: 2026-11-01.

This is a Phase 4 deliverable. Every knowledge version carries one MetadataRecord. The schema lives in code (`rag_core/knowledge/metadata.py`, the `FIELDS` list) and is repeated for people in `architecture/metadata_fields.csv`. A unit test fails if the two differ.

## Rules

1. Every value is text, so a record fits a CSV row and a SQLite column. Numbers and dates are written as text and checked.
2. A required field must be present and not empty. An empty optional field counts as missing and is dropped.
3. An unknown field is an error. A typo such as `confidentality` is caught at once, not discovered months later.
4. A record never changes. A change makes a new record (`with_changes`), and a new version stores it.
5. Each version has a full snapshot, because the proposal lets metadata change between versions (section 7.6).

## The fields

The first 13 rows are filled in by ingestion; the rest are optional fields the proposal lists for later phases.

| Field | Required | Rule | Meaning | Source |
| --- | --- | --- | --- | --- |
| `node_id` | yes | text | The node that owns the item. | proposal 7.5 (organization or node) |
| `title` | yes | text | The title of the item. | ingestion |
| `document_type` | yes | one of: document, profile, project_report, research_record, achievement_record, challenge_record, issue_answer, rfp, rfp_response, feedback_report, ike_model | The kind of knowledge (proposal section 7.1). | proposal 7.5 (document type) |
| `field_of_activity` | yes | text | The subject area, copied from the node unless given. | proposal 7.5 (field) |
| `confidentiality` | yes | one of: internal, confidential | Who may see it, copied from the node unless given. | proposal 7.5 (confidentiality level) |
| `language` | yes | text | Language code, such as en. | ingestion |
| `source_file` | yes | text | The file path, relative to the case-study documents folder. | proposal 7.3 (source document) |
| `file_format` | yes | one of: md, txt, docx, doc, pdf | The DocumentFormat of the file. | proposal 7.3 |
| `file_sha256` | yes | sha256 | ContentHash of the file's bytes. | proposal 7.7 (file hash) |
| `text_sha256` | yes | sha256 | ContentHash of the normalized extracted text. | proposal 7.7 (text normalization) |
| `extraction_method` | yes | one of: markdown, plain_text, docx_xml, pdf_text, doc_convert, lvm_ocr, pdf_mixed | How the text was read (pdf_mixed: some PDF pages from the text layer, the others by the LVM). | proposal 7.3 |
| `page_count` | no | int | Pages, when the format has pages. | proposal 7.4 (page number) |
| `ingested_at` | yes | date | When the version was registered, ISO 8601 in UTC. | ingestion |
| `change_reason` | no | text | Why this version was added. | proposal 7.6 (reason for change) |
| `subfield` | no | text | A narrower subject area. | proposal 7.5 |
| `project` | no | text | The project the item belongs to. | proposal 7.5 |
| `owner` | no | text | The author or owner. | proposal 7.5 |
| `status` | no | text | Workflow status. | proposal 7.5 |
| `priority` | no | text | Priority. | proposal 7.5 |
| `tags` | no | list | Labels, separated by ';'. | proposal 7.5 |
| `source_reliability` | no | one of: high, medium, low | How much the source can be trusted. | proposal 7.5 |
| `related_issue` | no | text | An issue id. | proposal 7.5 |
| `related_executor` | no | text | An executor id. | proposal 7.5 |
| `related_rfp` | no | text | An RFP id. | proposal 7.5 |
| `target_layer` | no | int | The layer a transfer of this item goes to. | proposal 7.5 |
| `suggested_detail_level` | no | one of: executive, managerial, technical_summary, detailed_technical | The detail level suggested for a transfer. | proposal 7.5 |

## What is not in the record, and why

The proposal also lists "initial version id" and "active version id" as metadata (section 7.5). They are not stored in the record, because the KnowledgeItem already knows them (its first version and its active tag). Storing them twice would let the two copies disagree.

## Two fingerprints

| Fingerprint | Of what | Equal means | Used for |
| --- | --- | --- | --- |
| `file_sha256` | the file's bytes | the very same file | spotting the same file sent twice |
| `text_sha256` | the extracted text, with whitespace runs made into one space | the same words in the same order, whatever the format | spotting an exact repeat (the D12 copy), and a DOCX copy of a Markdown file |

Case is kept in the text fingerprint on purpose: "US" and "us" may differ in meaning. Near duplicates (almost the same text) are found by the Phase 5 detector (`architecture/versioning_and_duplicates.md`).

## Example: D10 version 2 after ingestion

| Field | Value |
| --- | --- |
| node_id | N4 |
| title | Bus Fleet Inventory |
| document_type | document |
| field_of_activity | public transit |
| confidentiality | internal |
| language | en |
| source_file | N4_transit_agency/D10_bus_fleet_inventory_v2.md |
| file_format | md |
| extraction_method | markdown |
| ingested_at | the time of the run, such as 2026-11-01T10:00:00Z |
| file_sha256, text_sha256 | 64 hex characters each |

All 21 registered versions of the city are in `results/ingestion/phase4-words80/` (`catalog.csv` lists them; `knowledge.sqlite` holds the full records).
