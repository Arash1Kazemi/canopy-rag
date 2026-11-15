# Objectives and Scope

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Case study: the City (7 nodes in 4 layers).
Source: sections 2 and 4 of the proposal. Status: draft for supervisor review. Date: 2026-10-26.

## What this page decides

Objectives state what the city project must achieve, each in a form you can check with a yes or no. Scope is the fence: what the project builds, and what it deliberately refuses to build. Both come from sections 2 and 4 of the proposal. This is the first of four open Phase 1 items. The glossary, the metrics, and the unit-testing rules follow.

## Objectives

The proposal lists 20 objectives. They are grouped here into eight, and each one can be demonstrated with the city case study. The last column shows the proposal phases that build each objective; phases 1, 14 and 16 (discovery, tuning, final delivery) apply to all of them.

| ID | Objective | Built in phase |
| --- | --- | --- |
| O1 | **Cited answers.** A node answers questions from its own documents, with source citations, using small local models. When the answer is not there, it says "insufficient knowledge." | 8 |
| O2 | **Knowledge lifecycle.** DOC, DOCX and PDF files are ingested with metadata and split into chunks. A new version becomes the active one, old versions are kept, and duplicates and overlaps are detected. | 4, 5 |
| O3 | **Organization model.** Layers and nodes are defined in a registry, for any field of activity. A node can only use its own knowledge. | 6 |
| O4 | **Issues.** A node breaks a problem into sub-issues, compares it with existing issues, links it to knowledge and executors, suggests probable solutions, and tracks status and progress with fixed rules. | 7, 9 |
| O5 | **Projects, priorities and gaps.** A node records completed projects, research, achievements and challenges, ranks its key issues, and flags research gaps. | 12 |
| O6 | **Transfer and judge.** A node processes its knowledge in cycles and builds a transfer package at the detail level its parent's layer needs. An LLM judge scores it out of 20, and 18 or more is accepted. The parent can request the latest accepted package offline, stored as CSV or in a local database. | 10, 11 |
| O7 | **Engineering foundations.** The software follows Domain-Driven Design, runs fully offline, has unit tests for its domain logic, and has clear metrics for each main component, reviewed with the supervisor. | 2, 3, 15 |
| O8 | **RFP (built last).** An unsolved issue can produce a draft RFP. Proposals are evaluated against the RFP, and feedback is generated. The proposal makes this a core objective, so it is built in Phase 13 and not dropped. | 13 |


## Scope

The project covers the offline RAG core and the modules around it. It leaves out interfaces, cloud services, and any testing beyond unit tests.

### In scope

- An offline RAG core that runs with no network
- Local ingestion of DOC, DOCX and PDF files
- Small offline models: embeddings, LLMs (summaries, answers, issue analysis, RFPs, feedback), and LVMs for pages where layout or images matter
- Organizational nodes, a layer registry, and node boundaries
- The knowledge lifecycle: metadata, chunking, versions, and duplicate and overlap detection
- Issues, sub-issues, executors, and the relationships between them
- Cyclical node processing and transfer packages to the layer above, saved as CSV or in a local database
- Scoring with an LLM as judge
- Unit tests for domain logic, application services, scoring rules, chunking rules, relationship building, and prompt assembly
- Technical documentation, evaluation metrics, and project deliverables

### Out of scope

- A separate backend as a standalone product
- A separate frontend as a standalone product
- Hosting models in the cloud
- Any processing that depends on the internet
- Complex integration with enterprise identity systems
- Integration, end-to-end, browser, load, and penetration tests, and automated user evaluation (only unit tests are in scope)
- Real-time synchronization between nodes
- Training large foundation models from scratch
- Guaranteeing that every output is correct, beyond source citation, quality control, and the judge's score

Out of scope is not a weakness. When a friend asks for a web page, the answer is that a UI is out of scope, and the core offers functions a future UI can call.

Design principle from section 20 of the proposal (not a scope item): retrieval is limited to the node's own scope, transfer rules are limited per layer, and every answer can be traced to its source.

## Assumptions and checks

Each objective has a concrete check. The 26-question answer key tests objectives 1, 2, 3 and 5; unit tests and your own scoring cover the rest. Targets for each check are set in the metrics step, with the supervisor.

| Objective | How you check it | Answer-key questions |
| --- | --- | --- |
| O1 Cited answers | Run the answer key. Q04, Q05, Q07 to Q21 and Q25 need the right answer and source. Q06 must state the conflict between sources. Q22 to Q24 must be refused with "insufficient knowledge." | Q04, Q05, Q06, Q07, Q08, Q09, Q10, Q11, Q12, Q13, Q14, Q15, Q16, Q17, Q18, Q19, Q20, Q21, Q22, Q23, Q24, Q25 |
| O2 Knowledge lifecycle | Q01 and Q02 must give the version 2 figures. Q26 must give version 1 when asked for January. Q03 must cite the shift rules once, not twice. Unit tests cover versioning, chunk boundaries, and duplicate rules. | Q01, Q02, Q03, Q26 |
| O3 Organization model | The registry passes its rules: one root, and each layer is its parent's layer plus 1. Q22 is refused because N6 cannot see the Water Dept's documents. Q20, Q21 and Q24 test the terminal nodes. | Q20, Q21, Q22, Q24 |
| O4 Issues | Unit tests on status, progress, sub-issue, and relationship rules. Compare the suggested sub-issues for I01 with I02 to I04 in the issues file. | none (unit tests and own scoring) |
| O5 Projects, priorities and gaps | The system flags the Route 7 versus Route 12 conflict (Q06) and the missing metro budget (Q23) as research gaps. The ranking of the 7 issues is the same on every run. | Q06, Q23 |
| O6 Transfer and judge | Build packages up the chain from N6 to N4, N1, and N0. Score about 20 packages yourself, compare with the judge, and confirm a package under 18 is not sent. | none (unit tests and own scoring) |
| O7 Engineering foundations | Run with the network off. Run the unit tests with a stub in place of the LLM. Review the folder structure against the DDD design. Agree the metric targets with the supervisor. | none (unit tests and own scoring) |
| O8 RFP (built last) | Generate a draft RFP for I06, the unsolved issue. Check that every required section is present, and that each critique of a sample proposal points to an RFP criterion. | none (unit tests and own scoring) |

**Assumptions** (treated as true and written down so they can be checked; the one marked "Added by us" is not in the proposal):

- A set of documents, node definitions, layer information, and sample issues is prepared early. The city case study provides them.
- All AI models run locally in an offline environment.
- The main output is a software core that a future interface or operational layer can connect to.
- Evaluation uses measurable indicators, which are reviewed with the supervisor.
- The final list of organizations and nodes is fixed when the case study is defined. For the city that is done: seven nodes.
- Added by us, not in the proposal: your laptop can run a small local model.

## Risks

The proposal names eight risks, and the biggest is scope growth into a full platform.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| The scope grows into a full backend and frontend platform | High | Keep the focus on the RAG core and domain modules, and treat interfaces as future work |
| Offline models give weaker output than large cloud models | Medium to high | Controlled prompts, smaller workflows, strong retrieval, judge scoring, and human review of important outputs |
| DOC or PDF extraction quality varies | Medium | Several extraction strategies, metadata checks, chunk validation, and LVM help when needed |
| Users define their knowledge-transfer needs poorly | Medium | AI suggestions to tune the detail level, spot missing fields, and propose better transfer rules |
| Knowledge is duplicated or inconsistent | Medium | Duplicate and overlap detection, metadata normalization, and version control |
| Issue decomposition grows too broad | Medium | Limiting rules, relative position, priority indicators, and a human approval option |
| Judge scores are unstable | Medium | A structured rubric, a fixed score schema, prompt versioning, and calibration on samples |
| Organizational layers are not clearly defined | Medium | A layer registry template, reviewed with the supervisor in Phase 1 |

## Coverage of the proposal's 20 objectives

Every proposal objective maps to at least one project objective, so nothing was dropped when grouping.

| Proposal objective | Summary | Project objective |
| ---: | --- | --- |
| 1 | Domain-Driven Design architecture for knowledge, issues, executors and knowledge transfer | O7 |
| 2 | Offline RAG core using small local embedding, LLM and LVM models | O1, O7 |
| 3 | Ingest and process DOC, DOCX and PDF files | O2 |
| 4 | Define the organizational layers and the organizations and nodes in each layer | O3 |
| 5 | Let each layer define the knowledge it needs from its children | O6 |
| 6 | Use AI to improve, shorten, expand and summarize knowledge, and to suggest the detail level for transfer upward | O6 |
| 7 | Model completed projects, research, achievements, challenges, unsolved issues and research gaps | O5 |
| 8 | Keep very detailed knowledge in lower layers and transfer a suitable level of detail upward | O6 |
| 9 | Support an offline request from the upper layer for the latest prepared information | O6 |
| 10 | Process each node's knowledge in cycles and store the latest transferable output as CSV or in a local database | O6 |
| 11 | Issue decomposition, sub-issues, issue comparison and the Issue-Knowledge-Executor model | O4 |
| 12 | Produce a probable answer or solution for issues from the node's knowledge | O4 |
| 13 | Determine issue status and progress percentage | O4 |
| 14 | Identify and prioritize key issues and research gaps | O5 |
| 15 | Generate RFPs, manage proposals, evaluate proposals and generate automatic feedback | O8 |
| 16 | Support metadata with issue definition and knowledge registration | O2, O4 |
| 17 | Treat the system architecture and the Issue-Knowledge-Executor model as knowledge of each node | O4 |
| 18 | Support knowledge in any field of activity | O3 |
| 19 | Update, version, chunk, compare and de-duplicate knowledge | O2 |
| 20 | Define clear indicators to evaluate each main component, reviewed with the supervisor | O7 |

## To confirm with the supervisor

- The metric targets for each check above (set in the metrics step).
- The judge threshold of 18 out of 20, which is the proposal's default.
- The node and layer registry template (the proposal asks for this review in Phase 1).
- Hardware: whether the laptop has a GPU or runs on CPU only. Phase 2 confirms this.
