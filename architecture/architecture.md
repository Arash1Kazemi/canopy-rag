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
| Issue Management | Issues, sub-issues, status, progress, priority, comparison, relative position | `Issue` | Phase 7 (built) | `rag_core/issues/`, `rag_core/workflows/issues.py` |
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
| Domain | `shared/`, `organization/`, `knowledge/`, `rag/`, `issues/` | Entities, value objects, aggregates, domain services, repository interfaces | the standard library and other domain modules only |
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
| H07 | Issue status and progress follow fixed rules | `Issue` | `Issue.with_status` allows only the moves of `issues/status.py`; `compute_progress` in `issues/progress.py` (weights from config, A31); tests in `tests/test_core_issue_progress.py` |
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
| Create an issue, change its status, compare a draft, suggest and accept sub-issues | 7, built | issue data, a draft, or a parent issue and a language model | an `IssueResult`: done, or failed with the reason (nothing is saved on failure); `IssueService` in `workflows/issues.py` |
| Run a node cycle and build a transfer package | 11 | node | a judged package, sent or held |
| Draft an RFP, evaluate an RFP response | 13 | issue, RFP response | RFP, feedback report |

A use case is one class with one public method (`OrganizationService` groups the six small node and layer workflows in one class). It receives its repositories, models and clock as arguments (dependency injection), so a unit test can pass test doubles.

## 7. Storage abstractions

The proposal asks for a local database, a vector index, file storage and CSV output (sections 9.3 and 17). Each is behind an interface the domain defines:

| Interface | Adapters now | Later |
| --- | --- | --- |
| `KnowledgeRepository` (`knowledge/repository.py`) | `InMemoryKnowledgeRepository`, `SqliteKnowledgeRepository` | none needed |
| `HierarchyRepository` (`organization/repository.py`) | `CsvHierarchyRepository` (the registry files), `SqliteHierarchyRepository` (Phase 6), `InMemoryHierarchyRepository` | none needed |
| `IssueRepository` (`issues/repository.py`) | `InMemoryIssueRepository`, `SqliteIssueRepository` (Phase 7); the seed import in `infrastructure/issues_csv.py` | none needed |
| CSV output | `infrastructure/csv_export.py` (catalog and chunks) | transfer packages (Phase 11) |
| `VectorIndex` (`rag/vector_index.py`) | `InMemoryVectorIndex`, `SqliteVectorIndex` (Phase 8A): exact cosine search, the node filter applied before any score | none needed (the Phase 2 runner keeps its own in-memory list in `baseline_runner/retrieval.py`) |

SQLite comes with Python, needs no server and no download, and is one file, which suits an offline laptop. The same unit tests run against the in-memory and the SQLite repository (`tests/test_core_storage.py`), which shows they are interchangeable.

## 8. Domain events

Aggregates record what happened in an `events` list: `NodeAdded`, `KnowledgeVersionAdded`, `ActiveVersionChanged`. Nothing listens to them yet. Phase 11 uses them: a cycle looks for items whose active version changed since the last package. Recording them now costs one line per change and avoids a redesign later.

## 9. Folder layout

```
rag_core/
├── shared/kernel.py              shared kernel: DomainError, Confidentiality, TransferDetailLevel, TransferRule, DomainEvent
├── organization/                 Hierarchy (with the layer registry), Node, Layer, NodeIdentifier, LayerIndex; HierarchyRepository
├── knowledge/                    KnowledgeItem, KnowledgeVersion, KnowledgeChunk, value objects; metadata; chunking
├── rag/                          citation model, vector index, indexing, retrieval, context, answering (Phase 8A to 8C)
├── models/ports.py               EmbeddingModel, LanguageModel, VisionModel
├── ingestion/                    formats, extractors, samples, the ingestion use case, case-study requests
├── issues/                       Issue, IssueStatus, progress, node rules, comparison, suggestions (Phase 7)
├── workflows/                    the node and layer workflows (Phase 6), the issue workflows (Phase 7), the question workflow and the answer prompts (Phase 8)
├── infrastructure/               memory, SQLite (knowledge, hierarchy, issues, vectors), registry CSV, CSV export, Ollama (embedding, language, vision)
├── rag_wiring.py, evaluation.py, cli_rag.py     plain modules on top of the layers: the case-study wiring, the Phase 8D evaluation, the index, ask and evaluate commands
├── fakes.py                      test doubles for the core
└── __main__.py                   python -m rag_core ...
```

`baseline_runner/` stays: it is the Phase 2 experiment harness, and its results are the baseline. Phase 8 put retrieval and answering into `rag_core` and added `e3 --engine core` to the runner (decision A48). The full move, where the runner becomes a thin evaluation script, is not done: the grading and metric code still lives in `baseline_runner/` and `rag_core/evaluation.py` imports it. Moving it is a later step, best taken in Phase 14 when the held-out questions are used.

## 10. Decisions made in Phases 3 to 8

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
| A21 | The held-out set (`case_study/heldout_questions.csv`, ids HQ01 to HQ10) is read by no tuning step and is run once, at the end of Phase 14 | An honest final test (book Ch. 3 and 4: do not tune on the test set) | yes |
| A22 | Duplicate pair labels (`tests/fixtures/duplicates/pairs.csv`) are human judgements of intent, not detector scores; "exact" means the same text after whitespace is normalised | M10 and M11 need labels that do not come from the detector being measured | yes |
| A23 | The node directory (`rag_core/organization/directory.py`) raises `UnknownNodeError` for an unknown node instead of answering "not terminal" | A typo in a node id must fail loudly, not pass as a non-terminal node | yes |
| A24 | The Markdown files stay the source of truth; a real file is named in extra manifest columns (`real_file`, `real_format`) and never replaces `file` | The answer key and every earlier run read the Markdown; the real files test the readers | yes |
| A25 | Five real files: DOCX for D04 and D13, text PDF for D02 and D17, an image-only PDF for D19; no .doc; D10 and D12 stay Markdown | One of each format the proposal names, while the planted version and duplicate problems stay as they are | yes |
| A26 | D19 is a clean render of the Markdown, with no scan noise, so it is easier to read than a real scan | No scanner is available; a result on D19 is an upper bound for real scans | yes |
| A27 | Without a vision model, D19 falls back to its Markdown with a note; a PDF with a few empty pages is ingested with a warning, not failed | Ingestion must work on a laptop with no LVM running, and one blank page should not lose a document | yes |
| A28 | A PDF page has no text layer when it has fewer than 5 words | An untuned starting value: a page number or a header alone is not text | yes |
| A29 | Pages are rendered at 144 dpi in grey before the vision model reads them | An untuned starting value: readable text with small images on a 4 GB GPU | yes |
| A30 | Issues use the ten statuses of proposal 14.1 with a fixed table of allowed moves (`rag_core/issues/status.py`): work goes forward, a person may step back to analyzing, archived is the end. The old values map by meaning (`in progress` becomes `in_progress`) | The proposal names the statuses but not the moves; H07 needs fixed rules | yes |
| A31 | Progress uses the seven factors of proposal 14.1 (the build plan named five). Each factor is done or not, except sub-issues solved, which is a share. The weights are in `config/issue_progress_weights.csv`, add up to 100 and are untuned. Only a solved issue shows 100; any other shows at most 99. With no sub-issues, both sub-issue factors count zero | Fixed rules, same input same output (H07); the weights need the supervisor and data | yes |
| A32 | Priority is one of not set, low, medium, high; category is free text; the issue type is one of the five kinds in the glossary; the field of activity defaults to the node's | The proposal asks for a priority (12.1) but gives no scale | yes |
| A33 | A sub-issue and a blocked-by link stay inside one node, and neither parent nor blocked-by links may form a cycle. Siblings have different positions | An issue is modelled inside one node (glossary); a cycle has no order to work in | yes |
| A34 | A draft is compared with the issues of its own node only, by shared words (Jaccard) after stopwords are removed. Results are a ranked list with no threshold; a threshold waits for labelled issue pairs. A `similarity` slot takes embedding similarity in Phase 8 | Proposal 12: compare with the existing issues of the same node; do not choose a number before there is data to measure it | yes |
| A35 | Sub-issue suggestions come from the LLM with prompt P12 and are never saved on their own; a person accepts, edits or rejects, and the accepted ones are saved together in one transaction. The prompt never shows the existing sub-issues | A model reply must not create issues; M15 must not be leaked the answer | yes |
| A36 | Issues live in the `issues` table of `data/project.sqlite`. `case_study/issues.csv` is imported once, keeping ids, nodes, parents, titles and descriptions; the created date is the import time and the sibling position is the order in the file | One project database (build plan A0); the CSV is a reviewed seed, like the registry (A19) | yes |
| A37 | A node searches only its own chunks, not its parent's or its descendants' | Knowledge moves up only through transfer packages (proposal 8.4); every answer-key question is answerable only in its own node | yes |
| A38 | Only chunks of active versions are embedded; old vectors may stay in the index and retrieval filters them out | H04 keeps old versions; H01 filters before ranking | yes |
| A39 | The vector index is the durable record of the `indexed` chunk stage; stages are rebuilt from it after a restart, and `checked` blocks nothing | A12 kept stages in memory until Phase 8 | yes |
| A40 | Exact cosine search over all eligible vectors, ties broken by chunk id | The corpus is small; same input, same ranking | yes |
| A41 | Embedding batch size 16 (untuned) and default k = 3 (the Phase 2 baseline) | Comparable with the 2026-10-28 baseline | yes |
| A42 | A metadata filter means "equal", except `tags`, which means "is one of the labels" | Simplest rule that covers the metadata schema | yes |
| A43 | Tokens are estimated as the larger of words x 1.5 and characters / 3; there is no tokenizer in the core | Errs high; the baseline measured about 1.25 tokens per word | yes |
| A44 | An answer with no valid citation becomes "Insufficient knowledge." by default (`uncited_policy=refuse`); `mark` keeps it and flags it | H09 strictly; may lower M01 against the baseline, which kept uncited answers | yes |
| A45 | Context is filled in rank order and stops at the first chunk that does not fit; no chunk is cut; `min_score` has no default | A threshold number needs a source | yes |
| A46 | Indexing, retrieval and answering live in `rag_core/rag/` as pure use cases that take their ports as arguments; prompt files are loaded in `rag_core/workflows/` | The domain reads no files; architecture.md section 4 puts use cases in the application layer, so this is a deliberate exception | yes |
| A47 | Answer prompt P13 (v2) adds a conflict rule (report both documents) and "cite only files shown"; P01 stays the default until both are compared on the 26 questions | Q06 failed in the baseline; no prompt is promoted without a measurement | yes |
| A48 | The Phase 2 runner can give retrieval and answering to the core: `python -m baseline_runner e3 --engine core` (e3 only, default `baseline`). The move is not complete: E1, E2, E5, E6, the Phase 2 retrieval code and the grading and metric code stay in `baseline_runner`, and `rag_core/evaluation.py` calls that grading code | The Phase 2 results must stay reproducible, and the grading rules GR1 to GR5 should have one copy until Phase 14; a full move would touch results that are the baseline | yes |
| A49 | `evaluate` reads the case-study Markdown files (not the real DOCX and PDF), into its own `knowledge.sqlite` inside the results folder, and cuts chunks with `words80`. It differs from the Phase 2 run in three known ways: only active versions are indexed (no D10 v1, no D12 copy), citations are checked against the given chunks (H09), and an answer with no valid citation becomes a refusal (A44) | Same text and same chunks as the baseline, so a difference in the numbers comes from retrieval and answering, not from the files | yes |
| A50 | The baseline for the comparison is `results/e3-first` (the regraded files, the row of the same LLM id); M06 to M08 are computed from its rows the way the core run computes them; without that folder the `baseline` column of `metrics/metrics.csv` is used; a number that is missing on either side is shown as "not measured". M05 is never measured before Phase 10 | One honest table; no number is invented | yes |
| A51 | A setup problem exits with code 2 and one printed line, never a traceback: Ollama not reachable, a model not pulled, no index, a stale index, an unknown node or model id, an address that is not this machine (H06). A refusal is a result and exits with 0. `evaluate` will not write into a folder that already holds a run | A scripted run must tell "the system said no" from "the system could not run"; no result is overwritten | yes |
| A52 | Executor matching looks only in the issue's own node by default; scope "lineage" (ancestors and descendants) is opt-in | The proposal does not say; follows 12.1 and H01 | yes |
| A53 | An executor can be mapped to an issue only from the issue's node lineage, never from another branch | Keeps work inside the part of the tree that owns the issue | yes |
| A54 | The match score has four components (tags 60, documents 25, same node 15, availability 0), all untuned | No measured weights yet; availability is unknown in the data | yes |
| A55 | The tag share is the coverage of the executor's own tags, and a candidate needs at least one matched tag or document | A clear, explainable rule; it dilutes people with many tags | yes |
| A56 | "Author", "Project lead" and "Prepared by" lines in a document count as writing or owning it; attendee lists do not | Proposal 13.2 lists documents written | yes |
| A57 | Executor kinds are person, team, unit and capability; `people.csv` holds persons only | The glossary entry for Executor | yes |
| A58 | Mapping an executor does not change the issue status to "executor identified"; that stays a separate action | A status change is a person's decision (A30) | yes |
| A59 | Executors and IKE relations in terminal nodes are allowed | Issues there are already allowed | yes |
| A60 | Each IKE relation type allows exactly one source kind and one target kind | The wording of proposal 13.1 | yes |
| A61 | An "answer" in an IKE relation is an issue's answer or probable solution (12.5), keyed by the issue id | No separate answer entity exists yet | yes |
| A62 | "Similar" has no direction and is stored once; a duplicate relation is the same type, source and target | Avoids double edges | yes |
| A63 | Issues, answers and knowledge items stay in their own node; an executor may appear in another node's relation, but its expertise and project edges belong to its own node | D19 lists P02 of N4 at an N6 meeting | yes |
| A64 | Decomposes-into and blocked-by relations never form a cycle, and a sub-issue has one parent | Same rule as A33 | yes |
| A65 | `Issue.parent_issue_id` and `Issue.blocked_by` own those links; the IKE edges mirror them and are not synced automatically | One owner per fact | yes |
| A66 | The IKE seed (`case_study/ike_seed_relations.csv`, 38 relations) holds only relations stated in the records or a named document | No invented facts | yes |
| A67 | The M15 and M16 rubrics (`metrics/rubrics/`) use one rater, and a claim with no support scores at most 2 | A simple first version of a human form | yes |
