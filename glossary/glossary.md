# Glossary

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Source: the project proposal (sections 5.1 to 5.3 and the sections on knowledge, issues, transfer and judging). Status: draft for supervisor review. Date: 2026-10-26.

## What the glossary is

The glossary gives every important word in the project one meaning and one code name. In Domain-Driven Design this is the ubiquitous language: the same word is used in meetings with your supervisor, in documents, and in class names. It is the second open Phase 1 item, after scope and objectives, and it produces the initial glossary the project proposal asks for. Twenty-four of the 95 terms come from the proposal's own lists of entities and value objects. The other seventy-one are concepts the proposal describes in words, or that we added. Eight were added in Phase 3, when the domain model was designed, and Phase 3 also fixed the code names that were left open. Six were added in Phase 5, when versions, the chunk life cycle and duplicate detection were built, and two in Phase 6, when the layer registry was built (Transfer rule also became the value object TransferRule). Three were added on 2026-11-25, in Part A of the build plan: Node directory, Labelled pair and Held-out question. Four more were added that day for the real files of Phase 4: Real file, Image-only PDF, Text layer and Mixed PDF. Thirteen were added in Phase 7, when issues were built: IssueStatus, Issue type, Priority, Issue category, Issue dependency, RelativePosition, Progress factor, ProgressWeights, Issue comparison, IssueDraft, IssueMatch, Stopword and SubIssueSuggestion. Twelve were added in Phase 8, when retrieval and answering were built: VectorIndex, VectorRecord, IndexSignature, RetrievalHit, Metadata filter, Index rebuild, ContextHit, Context assembly, Context budget, Refusal reason, Uncited policy and AnswerPrompt. Two more were added with the Phase 8 evaluation: Evaluation run and Answer engine.

## How to read an entry

Each entry has four parts: the term, its meaning, its kind, and the words to avoid. The context column names the bounded context that owns the term.

- **Term:** the one English name used in code and in talk. Classes use PascalCase, such as KnowledgeItem.
- **Meaning:** one sentence.
- **Kind:** an entity has an identity that stays the same. A value object is defined only by its value. A concept is a word the domain uses that is not a class yet. The tag after a concept says where it comes from: "proposal text" means the proposal describes it in words, and "added by us" means it is not in the proposal. An entity or value object that is not in the proposal's own tables carries the same tag in `glossary.csv` (its `source` column).
- **Avoid:** words that must not be used for the same thing.

Four rules keep the language clean:

1. One concept has one term, and one term has one meaning.
2. If a word needs two meanings, split it into two terms.
3. Code names are English, singular, and PascalCase.
4. A bounded context owns each term. The same word cannot mean different things inside one context.

## The glossary

### Organization

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| Node | A company, organization, subsidiary, unit, project office, or other owner of operational knowledge. | Entity | Organizational Hierarchy | company, organization, office, unit (these are kinds of node) |
| NodeIdentifier | The stable id of a node. It never changes and is never reused. | Value object | Organizational Hierarchy | node name, node number |
| Layer | A level of the hierarchy that holds one or more nodes. | Entity | Organizational Hierarchy | level, tier, floor |
| LayerIndex | The position of a layer in the hierarchy. Layer 0 is the top. | Value object | Organizational Hierarchy | layer number, depth |
| Field of activity | The subject area a node works in, such as transport or water. | Concept (proposal text) | Organizational Hierarchy | domain, sphere |
| Terminal node | A node whose internal structure is not modeled. It appears as one black box. | Concept (added by us) | Organizational Hierarchy | leaf node |
| Hierarchy | The whole tree of one organization's layers and nodes. It is the aggregate that guards the tree rules: one root, each layer one below its parent, and no children under a terminal node. | Entity | Organizational Hierarchy | org chart, tree |
| Layer registry | The record of every layer: its number, its name and role, its member nodes, and its transfer rule. | Concept (proposal text) | Organizational Hierarchy | layer table, level list |
| Layer membership | Which layer a node belongs to. It follows from the node's parent: the parent's layer plus one. | Concept (proposal text) | Organizational Hierarchy | layer assignment, node level |
| Node directory | A read-only lookup that says whether a node exists and whether it is terminal. Code checks a node id through it, never by comparing strings. | Concept (added by us) | Organizational Hierarchy | node list, node table |

### Knowledge

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| KnowledgeItem | A controlled source of knowledge, such as a document, profile, project report, or issue answer. | Entity | Knowledge Management | document, file, record (a document is one kind of item) |
| KnowledgeItemId | The stable id of a knowledge item, such as D10. It never changes and is never reused. | Value object | Knowledge Management | document number, file name |
| KnowledgeVersion | One specific version of a knowledge item. An update adds a version and never deletes an old one. | Entity | Knowledge Management | revision, copy |
| VersionTag | The unchangeable id of a version, such as v2. | Value object | Knowledge Management | version name |
| Active version | The version of an item that retrieval uses by default. Our rule: exactly one per item. | Concept (proposal text) | Knowledge Management | current version, latest version |
| KnowledgeChunk | A small, retrievable piece of a knowledge version, used by RAG. | Entity | Knowledge Management | fragment, passage, snippet |
| MetadataRecord | Structured data about a knowledge item or an issue, such as node, type, or confidentiality. | Value object | Knowledge Management | tags, properties |
| KnowledgeScope | The field of activity, confidentiality level, and allowed usage range of a knowledge item. | Value object | Knowledge Management | access level, permissions |
| ContentHash | A SHA-256 fingerprint of a file's bytes or of its normalized text. Equal fingerprints mean equal content. | Value object | Knowledge Management | checksum, signature |
| DocumentFormat | The kind of file a knowledge version was read from: Markdown, plain text, DOCX, DOC, or PDF. | Value object | Knowledge Management | file type, extension |
| SourceLocation | Where a chunk comes from: the item, the version, the file, the pages, the heading path, and the character span. | Value object | Knowledge Management | position, pointer |
| ChunkingPolicy | The rule for cutting a version into chunks: the chunk size and overlap in words, and whether a chunk stays inside one section. | Value object | Knowledge Management | chunk config, splitter settings |
| Duplicate | Knowledge that repeats other knowledge. Exact means the same content, near means almost the same. A partial repeat is an overlap. | Concept (proposal text) | Knowledge Management | copy, clone |
| Text extraction | Reading the text and its structure (headings, pages, tables) out of a file, with a parser or, for a scan, with the LVM. | Concept (proposal text) | Knowledge Management | parsing, conversion |
| Ingestion | Registering a file as a new knowledge item or a new version: detect the format, extract the text, record the metadata, chunk, and store. | Concept (proposal text) | Knowledge Management | upload, import |
| Near duplicate | Two documents in different items whose text is almost the same, for example a copy with a few words changed. | Concept (proposal text) | Knowledge Management | similar document, fuzzy copy |
| Overlap | A part of one document that also appears in another, while the two documents as a whole differ. | Concept (proposal text) | Knowledge Management | partial copy, shared section |
| DuplicateRecord | One finding that two versions in different items repeat each other: the kind (exact, near or overlap), a similarity score, and the evidence. | Value object | Knowledge Management | match, hit, finding |
| DuplicatePolicy | The settings of duplicate detection: the size of a word group and the similarity limits for a near duplicate and an overlap. | Value object | Knowledge Management | duplicate config, detector settings |
| ChunkStage | Where a chunk is in its life cycle: created, embedded, checked for duplicates, or indexed. | Value object | Knowledge Management | chunk status, chunk state |
| Change summary | A short machine-written note of what changed between a version and the one registered before it. | Concept (added by us) | Knowledge Management | diff, changelog |
| Labelled pair | Two texts with a human label (exact, near, overlap or different), used to measure duplicate detection. | Concept (added by us) | Knowledge Management | test pair, sample pair |
| Real file | A DOCX or PDF made from a case-study Markdown source, named in the manifest's `real_file` column. | Concept (added by us) | Knowledge Management | converted copy, sample file |
| Image-only PDF | A PDF whose pages are only pictures, with no text layer, like a scan. | Concept (added by us) | Knowledge Management | scanned PDF, image PDF |
| Text layer | The text a PDF stores, which a reader can pull out without a vision model. | Concept (added by us) | Knowledge Management | OCR text, hidden text |
| Mixed PDF | A PDF with both text pages and scanned pages, read page by page. | Concept (added by us) | Knowledge Management | hybrid PDF, partly scanned PDF |

### RAG

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| RetrievalQuery | The normalized form of a question from a user or the system, used to search. | Value object | RAG Core | prompt (a prompt is the whole text sent to the model) |
| SimilarityScore | How close a chunk is to a query in vector or hybrid retrieval. | Value object | RAG Core | relevance, confidence |
| Citation | A link from a claim in an answer to its source: the file, and when known the chunk and page. | Value object | RAG Core | reference, footnote |
| VectorIndex | The stored chunk vectors with exact cosine search. It filters by node, active version and metadata before it ranks anything. | Entity | RAG Core | vector store, vector database |
| VectorRecord | One chunk's vector with its chunk, item, version, node, embedding model and chunking policy. | Value object | RAG Core | embedding row, vector entry |
| IndexSignature | The embedding model tag plus the chunking policy of an index. When either changes, the index is rebuilt. | Value object | RAG Core | index version, index key |
| RetrievalHit | One ranked chunk returned by retrieval, with its score and its source location. | Value object | RAG Core | search result, match |
| Metadata filter | Conditions on version metadata that remove chunks before ranking, never after. | Concept (proposal text) | RAG Core | post-filter, search filter |
| Index rebuild | Dropping all vectors and embedding again because the index signature changed. | Concept (added by us) | RAG Core | reindex, refresh |
| ContextHit | A ranked chunk in the form the answer step needs: id, text, file stem, score and pages. | Value object | RAG Core | snippet, passage |
| Context assembly | Filling the answer prompt with ranked chunks in rank order within a token budget, never cutting a chunk. | Concept (added by us) | RAG Core | stuffing, packing |
| Context budget | The tokens left for chunks after the model window, the room for the reply and the fixed prompt text. | Concept (added by us) | RAG Core | context size, window |
| Refusal reason | Why an answer is "insufficient knowledge": no evidence, context too small, the model refused, or no valid citation. | Concept (added by us) | RAG Core | error code, failure |
| Uncited policy | What happens to an answer with no valid citation: refuse it (the default) or keep it and mark it uncited. | Concept (added by us) | RAG Core | citation mode |
| Answer engine | The code that retrieves and answers in an evaluation run: the Phase 2 runner's own code (baseline) or the rag_core use cases (core). | Concept (added by us) | RAG Core | backend, mode, pipeline |

### Issues and executors

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| Issue | A problem, question, need, research gap, or operational concern modeled inside one node. | Entity | Issue Management | ticket, task, bug |
| SubIssue | An issue derived from a parent issue, with its own status and relationships. | Entity | Issue Management | subtask, child task |
| ProgressPercentage | How far an issue has come, from 0 to 100, calculated by fixed rules. | Value object | Issue Management | completion, percent done |
| Executor | A person, team, unit, or organizational capability that can help solve an issue. | Entity | Executor Management | assignee, owner, worker |
| Issue-Knowledge-Executor model | The graph of typed relationships between issues, knowledge, and executors, such as "issue depends on knowledge". Short form: IKE model. | Concept (proposal text) | Issue-Knowledge-Executor | knowledge graph |
| Research gap | A hole in a node's knowledge: nothing relevant, outdated, conflicting, not answerable with confidence, or a judge score below the threshold. | Concept (proposal text) | Issue Management | missing info, unknown |
| IssueStatus | Where an issue stands, one of the ten values of proposal 14.1: new, analyzing, knowledge identified, executor identified, solution proposed, in progress, awaiting decision, solved, unsolved, archived. Only the moves in a fixed table are allowed. | Value object | Issue Management | state, stage, phase |
| Issue type | What kind of issue it is: a problem, a question, a need, a research gap or an operational concern. | Concept (proposal text) | Issue Management | kind, class |
| Priority | How soon an issue should be worked on: not set, low, medium or high (a working scale until the supervisor decides). | Concept (proposal text) | Issue Management | urgency, severity, importance |
| Issue category | A label that groups related issues inside one node, such as data or capacity. It is not the node's field of activity. | Concept (proposal text) | Issue Management | tag, type, field |
| Issue dependency | A blocked-by link: one issue waits for another issue of the same node. The links never form a cycle. | Concept (proposal text) | Issue Management | prerequisite, predecessor |
| RelativePosition | Where an issue stands among the issues of its node: its parent, its position among its siblings, its sub-issues, what blocks it, what it blocks, and the issues of the same category. | Value object | Issue Management | rank, order |
| Progress factor | One of the seven things proposal 14.1 counts as progress, such as sub-issues defined or a solution proposed. Each is done or not done; sub-issues solved is a share. | Concept (proposal text) | Issue Management | criterion, KPI |
| ProgressWeights | One whole-number weight per progress factor, adding up to 100, read from config/issue_progress_weights.csv. The values are untuned. | Value object | Issue Management | scores, coefficients |
| Issue comparison | Ranking the existing issues of the same node by how much they resemble a draft: shared words after stopwords are removed, and embedding similarity from Phase 8. There is no threshold yet. | Concept (proposal text) | Issue Management | deduplication, search |
| IssueDraft | A new issue that is not saved yet, in the node where it would live. It is compared with the existing issues. | Value object | Issue Management | proposal, candidate |
| IssueMatch | One existing issue of the same node that resembles a draft, with its score and the words they share. | Value object | Issue Management | duplicate, hit |
| Stopword | A small common word, such as the or on, that is removed before two texts are compared. | Concept (added by us) | Issue Management | filler word, noise word |
| SubIssueSuggestion | A sub-issue that the language model proposes. It becomes a SubIssue only when a person accepts it, as it is or edited. | Value object | Issue Management | generated issue, AI issue |

### Transfer

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| TransferPackage | Prepared knowledge sent from a lower layer to the layer above. | Entity | Knowledge Transfer | report, bundle, export |
| TransferDetailLevel | How detailed a package is: executive, managerial, technical summary, or detailed technical. | Value object | Knowledge Transfer | verbosity, summary level |
| TransferRule | A layer's requirements for what it receives: topics, detail level, required fields, minimum judge score, maximum length, citation level. It is set per layer in the layer registry. | Value object | Knowledge Transfer | template, policy |
| Cycle | One run of a node's processing: find changes, re-index, update issues, build and judge a package. A trigger starts it. | Concept (proposal text) | Knowledge Transfer | batch, job, sync |

### Judging

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| JudgeScore | The structured score from the LLM judge, with pass or fail and an explanation. | Entity | Evaluation and Judging | grade, rating |
| JudgeRubric | The scoring framework the judge applies, worth 20 points in total. | Value object | Evaluation and Judging | checklist, criteria sheet |
| JudgeThreshold | The minimum accepted score, such as 18 out of 20. | Value object | Evaluation and Judging | cut-off, limit |
| Metric | A named rule that turns how well one component works into a number, such as the share of questions answered correctly. The proposal calls it an indicator. | Concept (proposal text) | Evaluation and Judging | indicator, KPI, score (a score belongs to the judge) |
| Baseline | The value of a metric on the simplest working version, measured before any tuning. Later versions must beat it. | Concept (added by us) | Evaluation and Judging | starting point, benchmark |
| Target | The value a metric must reach to count as good enough. It is agreed with the supervisor, and only after a baseline exists. | Concept (added by us) | Evaluation and Judging | goal, pass mark, threshold (a threshold is the JudgeThreshold) |
| Grading rule | The written rule that decides whether one answer to one answer-key question is correct. It gives the same result on every run. | Concept (added by us) | Evaluation and Judging | scoring function, checker, matcher |
| Hard rule | A rule that must hold on every run. It is checked as pass or fail, not measured as a percentage. Example: a node never uses another node's documents. | Concept (added by us) | Evaluation and Judging | invariant, constraint, requirement |
| Test double | A simple stand-in for a real part in a unit test, such as a stub that returns a fixed answer in place of the LLM. | Concept (added by us) | Evaluation and Judging | mock, dummy (these are kinds of test double) |
| Held-out question | A test question kept apart from the answer key. No tuning step may read it; it is run once, at the end of Phase 14. | Concept (added by us) | Evaluation and Judging | test question, hidden question |
| Evaluation run | One pass of the 26 answer-key questions through a system, graded with the grading rules and summarized as metrics, saved in one results folder. | Concept (added by us) | Evaluation and Judging | benchmark run, test run (a test run is a unit test) |

### Models and prompts

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| Prompt template | A versioned prompt with blanks, one per task type, kept in a registry. | Concept (proposal text) | Model and Prompt Management | script, form letter |
| Model registry | A record of the local models in use: their task, limits, and evaluation notes. | Concept (proposal text) | Model and Prompt Management | model list, model config |
| Embedding model | A local model that turns a piece of text into a list of numbers, so that texts with similar meaning get close lists. | Concept (proposal text) | Model and Prompt Management | encoder, vectorizer, embedder |
| LLM | The local large language model that writes answers and summaries from retrieved chunks. The judge also runs on it. | Concept (proposal text) | Model and Prompt Management | chat model, generator, bot |
| LVM | The local vision-language model that reads page images, such as a scanned document, and returns text. Reading text from an image (OCR) is one of its tasks. | Concept (proposal text) | Model and Prompt Management | OCR engine, image model |
| Quantization | Storing a model's numbers with fewer bits so the file is smaller and runs faster, at a small cost in quality. Shown as Q4 or Q8 in model names. | Concept (added by us) | Model and Prompt Management | compression, shrinking |
| AnswerPrompt | A versioned answer prompt template with its registry id, such as P01 or P13. | Value object | Model and Prompt Management | system prompt, instructions |

### RFP

| Term | Meaning | Kind | Context | Avoid |
| --- | --- | --- | --- | --- |
| RFP | A request for proposals that the system writes to invite solutions to an unsolved issue. | Entity | RFP and Proposal Management | tender, call |
| Proposal | A submission that answers an RFP and is evaluated against it. In prose, call it an RFP response. | Entity | RFP and Proposal Management | bid, offer; "proposal" alone for the project document |
| FeedbackReport | A structured report on a proposal: strengths, weaknesses, missing requirements, and a recommendation. | Entity | RFP and Proposal Management | review, comments |

## Decisions to confirm

| Word | Open question | Our default |
| --- | --- | --- |
| Proposal | "Proposal" is the class for an RFP response, but "the proposal" also names the project document. | In prose we write "the project proposal" for the document and "RFP response" for the entity. In code it stays Proposal. Earlier pages say "the proposal" and mean the project document. |
| Issue | One word covers a problem, question, need, research gap, and operational concern. | One Issue class with a type field, not five classes. |
| Executor | The proposal includes organizational capabilities, not only people. | Keep it as in the proposal. |
| Terminal node | This term is not in the proposal. | Keep it, and confirm it with the supervisor. |
| Detail level names | The proposal's four level names need fixed English names. | executive, managerial, technical summary, detailed technical. |
| Test double | It is an engineering word, not a proposal word, and none of the proposal's bounded contexts owns it. | Keep it in Evaluation and Judging, and confirm with the supervisor. |
