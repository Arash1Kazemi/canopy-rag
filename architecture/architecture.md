# DDD architecture

Project: offline hierarchical RAG core. Source: Phase 3 of the project proposal (sections 5, 9.3, 17, 18 and 21). Status: draft for supervisor review. Date: 2026-11-01.

This is the first Phase 3 deliverable, the DDD architecture document. The other two are `architecture/domain_model.md` (the domain model specification) and `architecture/unit_test_plan.md` (the first unit-test plan). The code that follows this design is in `rag_core/`.

## 1. The idea in one paragraph

The system is split into ten bounded contexts, the proposal's own list. Each context owns its words and its rules. Inside a context, an **aggregate** is the one object that guards a group of rules: every change goes through it, so a rule cannot be skipped. The code has four layers. The inner layer (the domain) is plain Python with the rules and nothing else: no files, no database, no network, no model. The outer layers bring in files, SQLite and Ollama through small interfaces. This keeps the rules easy to test, which matters because the proposal limits software testing to unit tests (section 18).

## 2. The bounded contexts

| Context | Owns | Aggregate root | Built in | Code |
| --- | --- | --- | --- | --- |
| Organizational Hierarchy | Nodes, layers, parent and child, terminal nodes | `Hierarchy` | Phases 3 and 6 (built) | `rag_core/organization/`, `rag_core/workflows/` |
| Knowledge Management | Knowledge items, versions, chunks, metadata, source locations, duplicates | `KnowledgeItem` | Phases 3 to 5 | `rag_core/knowledge/`, `rag_core/ingestion/` |
| RAG Core | Retrieval, context assembly, prompts, cited answers | none (domain services) | Phase 4 citations, Phase 8 the rest | `rag_core/rag/` |
| Issue Management | Issues, sub-issues, status, progress, priority | `Issue` | Phase 7 | Phase 7, in progress; code in `rag_core/issues/` |
| Executor Management | Executor profiles, expertise, matching | `Executor` | Phase 9 | planned |
| Issue-Knowledge-Executor | Typed relations between issues, knowledge and executors | the IKE model (`ike_model`; its classes come in Phase 9) | Phase 9 | planned |
| Knowledge Transfer | Cycles, transfer packages, detail levels. The `TransferRule` value is in the shared kernel; the layer registry stores it | `TransferPackage` | Phase 11 | planned |
| Evaluation and Judging | Rubrics, judge scores, thresholds | `JudgeScore` | Phase 10 | planned |
| RFP and Proposal Management | RFPs, RFP responses, feedback | `RFP` | Phase 13 | planned |
| Model and Prompt Management | Model registry, prompt templates, model ports | none (registries) | Phase 2 data, Phase 3 ports | `rag_core/models/`, `models/`, `prompts/` |

"Planned" contexts are designed in `architecture/domain_model.md` (their aggregates and the rules they will own), but they have no code yet. Code without a use is not written ahead of its phase.

## 3. How the contexts depend on each other (context map)

```
                    Organizational Hierarchy  (upstream of everything: every item, issue and package belongs to a node)
                               |
        +----------------------+----------------------+
        |                      |                      |
 Knowledge Management ---> RAG Core           Issue Management ---> Executor Management
        |  (chunks, citations)  |                      |                 |
        |                       |                      +----> Issue-Knowledge-Executor <----+
        +-----------------------+----------------------------------------^
                               |
                    Knowledge Transfer ---> Evaluation and Judging  (a package is judged before it is sent)
                               |
                    RFP and Proposal Management  (built last, reads issues and knowledge)

 Model and Prompt Management: a supplier to RAG Core, Ingestion (the LVM), Judging and RFP, through ports.
 Shared kernel (rag_core/shared/kernel.py): DomainError, Confidentiality, TransferDetailLevel, DomainEvent.
```

Rules of the map:

1. An arrow means "uses". The context at the tail reads the other one's published objects or ids. It never changes them.
2. Contexts refer to each other by id (a node id, an item id), not by holding the other context's objects. For example, a `KnowledgeItem` stores `node_id`, not a `Node`.
3. The shared kernel stays tiny. A word moves there only when two contexts must mean exactly the same thing by it.

## 4. Layers and the dependency rule

| Layer | Folder | Holds | May import |
| --- | --- | --- | --- |
| Domain | `shared/`, `organization/`, `knowledge/`, `rag/` | Entities, value objects, aggregates, domain services, repository interfaces | the standard library and other domain modules only |
| Ports | `models/` | The shapes of the local models (embedding, LLM, LVM) | the standard library |
| Application | `ingestion/`, `workflows/` (later also `answering/`, `transfer/` ...) | Use cases: coordinate the domain, read files, return results | the domain and the ports |
| Infrastructure | `infrastructure/` | Adapters: in-memory and SQLite repositories, the registry CSV, CSV export, Ollama | everything |
| Interface | `__main__.py` | The command line | everything |

**The dependency rule:** an inner layer never imports an outer one. `tests/test_core_architecture.py` reads the imports of every domain file and fails if one breaks the rule, so the rule is checked, not only written.

Why the application layer may read files: ingestion is about files, so its use case opens them. What it never does is choose a database or call Ollama directly; those come in as arguments.

## 5. Aggregates and the hard rules they own

A hard rule belongs to the object that can see everything the rule talks about. This table is the key Phase 3 decision.

| Rule | Statement (short) | Owner | Where it is enforced now |
| --- | --- | --- | --- |
| H01 | A node answers only from its own documents | RAG Core retrieval, using `node_id` on every chunk | Every `KnowledgeChunk` carries its node; `active_chunks(node_id)` filters by it. The retrieval service comes in Phase 8. |
| H02 | One root; each layer is its parent's plus 1 | `Hierarchy` | `Hierarchy.add_node` and `Hierarchy.move_node` |
| H03 | Exactly one active version per item | `KnowledgeItem` | `KnowledgeItem` (constructor, `add_version`, `activate`) |
| H04 | An update adds a version, never deletes one | `KnowledgeItem`, and the repositories | No remove method; repositories refuse a missing version; SQLite triggers refuse UPDATE and DELETE on versions |
| H05 | A package below the threshold is never sent up | `TransferPackage` with a `JudgeThreshold` | Phase 11 |
| H06 | Runs with the network off | Infrastructure (only `127.0.0.1`) | The Ollama client talks to 127.0.0.1; the test fixture blocks all other connections |
| H07 | Issue status and progress follow fixed rules | `Issue` | Phase 7 |
| H08 | The ranking of issues is the same on every run | Issue prioritization service | Phase 12 |
| H09 | Every answer cites a source or refuses | RAG Core answer formatter | Citation model now (`rag_core/rag/citation.py`); the formatter in Phase 8 |
| H10 | A terminal node has one summary document and no children | `Hierarchy` (no children) and the ingestion use case (one document) | `Hierarchy.add_node`, `move_node` and `set_terminal` refuse a child under a terminal node; `IngestionService` refuses a second item in a terminal node; the make-terminal workflow refuses a node that has two items |

H10 has two halves with two owners. "No children" is a tree rule, so `Hierarchy` owns it. "One summary document" spans two aggregates (a node and the items of that node), so no single aggregate can see it; the use case that adds items checks it. This is the usual DDD answer when a rule crosses aggregates.

## 6. Application services (use cases)

| Use case | Phase | Input | Output |
| --- | --- | --- | --- |
| Register a file (ingestion) | 4, built | file, item id, node, version tag, title | an `IngestionResult`: new item, new version, skipped repeat, or failed with the reason |
| Re-chunk with another policy | 5 | policy | a new database from a new ingestion run (A11); stored versions are never edited |
| Detect duplicates and overlaps | 5, built | an item or all items | duplicate and overlap records (`find-duplicates`) |
| Define, move, make terminal, or change a node; define a layer or set its rule | 6, built | node and parent, or layer and rule | a `WorkflowResult`: done, or failed with the reason (nothing is saved on failure) |
| Answer a question in a node | 8 | question, node | answer with citations, or "insufficient knowledge" |
| Create an issue, split it into sub-issues | 7 | issue data | issue and sub-issues |
| Run a node cycle and build a transfer package | 11 | node | a judged package, sent or held |
| Draft an RFP, evaluate an RFP response | 13 | issue, RFP response | RFP, feedback report |

A use case is one class with one public method (`OrganizationService` groups the six small node and layer workflows in one class). It receives its repositories, models and clock as arguments (dependency injection), so a unit test can pass test doubles.

## 7. Storage abstractions

The proposal asks for a local database, a vector index, file storage and CSV output (sections 9.3 and 17). Each is behind an interface the domain defines:

| Interface | Adapters now | Later |
| --- | --- | --- |
| `KnowledgeRepository` (`knowledge/repository.py`) | `InMemoryKnowledgeRepository`, `SqliteKnowledgeRepository` | none needed |
| `HierarchyRepository` (`organization/repository.py`) | `CsvHierarchyRepository` (the registry files), `SqliteHierarchyRepository` (Phase 6), `InMemoryHierarchyRepository` | none needed |
| CSV output | `infrastructure/csv_export.py` (catalog and chunks) | transfer packages (Phase 11) |
| Vector index | none yet (Phase 2 used an in-memory list in `baseline_runner/retrieval.py`) | a `VectorIndex` interface in Phase 8 |

SQLite comes with Python, needs no server and no download, and is one file, which suits an offline laptop. The same unit tests run against the in-memory and the SQLite repository (`tests/test_core_storage.py`), which shows they are interchangeable.

## 8. Domain events

Aggregates record what happened in an `events` list: `NodeAdded`, `KnowledgeVersionAdded`, `ActiveVersionChanged`. Nothing listens to them yet. Phase 11 uses them: a cycle looks for items whose active version changed since the last package. Recording them now costs one line per change and avoids a redesign later.

## 9. Folder layout

```
rag_core/
├── shared/kernel.py              shared kernel: DomainError, Confidentiality, TransferDetailLevel, TransferRule, DomainEvent
├── organization/                 Hierarchy (with the layer registry), Node, Layer, NodeIdentifier, LayerIndex; HierarchyRepository
├── knowledge/                    KnowledgeItem, KnowledgeVersion, KnowledgeChunk, value objects; metadata; chunking
├── rag/citation.py               the citation model
├── models/ports.py               EmbeddingModel, LanguageModel, VisionModel
├── ingestion/                    formats, extractors, samples, the ingestion use case, case-study requests
├── workflows/                    the node and layer workflows (Phase 6)
├── infrastructure/               memory, SQLite (knowledge and hierarchy), registry CSV, CSV export, Ollama vision
├── fakes.py                      test doubles for the core
└── __main__.py                   python -m rag_core ...
```

`baseline_runner/` stays as it is: it is the Phase 2 experiment harness, and its results are the baseline. Phase 8 moves retrieval and answering into `rag_core` behind the same metrics, and the Phase 2 runner then becomes a thin evaluation script.

## 10. Decisions made in Phases 3, 5 and 6

| # | Decision | Why | To confirm |
| --- | --- | --- | --- |
| A1 | Python, plain classes, no framework | The baseline is Python; a framework adds nothing the rules need | no |
| A2 | SQLite for the local database | Built into Python, one file, offline | yes |
| A3 | An item's id is the document id (`D10`); a version tag is the manifest version (`2`) | Stable, already in the manifest | no |
| A4 | The newest version by natural tag order becomes active; an older one registered late does not | Fixes the D10 order problem without asking the user | yes |
| A5 | Each version holds a full metadata snapshot | The proposal says metadata can change per version (section 7.6) | no |
| A6 | An exact repeat of a version's text is skipped at ingestion | Keeps the D12 copy out of the index; near duplicates and overlaps are advice only (A13) | yes |
| A7 | Answers keep citing file stems; a citation built from a chunk also carries the chunk, pages and headings | The grading rules GR4 and GR5 work on stems | no |
| A8 | The default chunking stays the Phase 2 baseline (`words80`) | It is the measured one; `sections80` waits for an experiment | yes |
| A9 | H10 "one summary document" is checked in the ingestion use case | The rule spans two aggregates | yes |
| A10 | New glossary classes may come from proposal text or be added by us | Phase 3 needed 7 classes the proposal's tables do not list | yes |
| A11 | Re-chunking with another policy is a new ingestion run into a new database; stored versions are never edited | H04, and it keeps the `words80` and `sections80` runs apart | yes |
| A12 | Chunk stages (created, embedded, checked, indexed) are kept in memory until Phase 8; a chunk is retrievable only if it is indexed and its version is active | The embedding and the index do not exist yet | yes |
| A13 | Near duplicates and overlaps are findings for a person; nothing is merged, hidden or deleted | A wrong merge loses knowledge, and H04 forbids deleting a version | yes |
| A14 | Duplicate detection compares different items only, and active versions by default | Versions of one item are meant to be similar | yes |
| A15 | The starting policy: word groups of 5, near at resemblance 0.8, overlap at 20 shared groups | Chosen from `scripts/duplicate_experiment.py`; not tuned (`architecture/versioning_and_duplicates.md`) | yes |
| A16 | The transfer rule belongs to the receiving layer; a node's reporting format and minimum score copy the rule of its parent's layer, are re-derived on a move or a rule change, and a check keeps them equal | One source of truth for what a layer needs | yes |
| A17 | A node can move to a new parent; its whole subtree moves and shifts layers. The root, a move under itself or a descendant, and a move under a terminal node are refused | H02 and H10 stay true after every change | yes |
| A18 | Nodes are never deleted and an id is never reused; retiring a node is a later decision | The proposal asks for no deletion; knowledge belongs to a node | yes |
| A19 | The registry CSV files seed a hierarchy database (`init-hierarchy`); after that the database is the truth | Nodes must change at run time without editing a reviewed file | yes |
| A20 | Only the detail level, the minimum judge score and the topics of proposal section 6.4 are filled in; excluded topics, required fields, output format, maximum length and citation level stay empty until the supervisor decides | No invented values (`architecture/hierarchy_and_layers.md`) | yes |
