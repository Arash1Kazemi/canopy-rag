# Domain discovery report

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Case study: the City (7 nodes in 4 layers).
Source: the project proposal in `source/technical-proposal-offline-hierarchical-rag-fa.md` (Persian, 16 phases). Status: draft for supervisor review. Date: 2026-10-26.

## 1. Summary

Phase 1 answers four questions before any model is run: what the system is for, what the organization it serves looks like, what words and numbers we will use to talk about it, and how we will know it works. The answers are in files, and `python tools/run_checks.py` keeps them consistent.

- **The system** keeps knowledge inside each node of an organization, answers questions from that node's own documents with citations, tracks the node's issues, and sends a judged summary up to the layer above, all offline on small local models.
- **The case study** is a made-up city with 7 nodes, 20 documents in 22 files, 7 issues, 6 people and 26 test questions. It contains planted problems on purpose.
- **The vocabulary** has 61 terms with one meaning each.
- **The success measures** are 28 metrics and 10 hard rules. No target is set yet, because targets need a baseline from Phase 2.
- **The testing approach** separates unit tests (our rules) from evaluation (the models).

## 2. The domain

An organization is a tree. A company has subsidiaries, a subsidiary has units, a unit has projects. Each owner of knowledge is a node, and every node holds documents, runs into issues, and must report upward. Detail gets coarser on the way up: a project knows the technical details, and the top only needs an executive summary. Today this is done by people writing reports, which is slow and loses facts. The proposal builds the same flow with software that is offline, so confidential documents never leave the node.

Three ideas carry the whole project:

1. **Knowledge stays at the node.** A node answers only from its own documents (hard rule H01).
2. **Issues connect knowledge to people.** An issue links to the knowledge that explains it and to the executors who can solve it.
3. **Reports climb one layer at a time.** A node builds a package at the detail level its parent needs, a judge scores it out of 20, and only a package of 18 or more is sent.

## 3. The organization model

```
N0 City Council (layer 0)
├── N1 Transport Dept (layer 1)
│   └── N4 Transit Agency (layer 2)
│       └── N6 Bus Network Project (layer 3)
├── N2 Water Dept (layer 1)
│   └── N5 Water Utility (layer 2, terminal)
└── N3 Housing Dept (layer 1, terminal)
```

The registry is `registry/node_layer_registry.csv`, and its columns are explained in `registry/README.md`. Its rules are: one root, each layer is its parent's layer plus 1, and a terminal node is a black box with one summary document. Layer 3 sends a technical summary, layer 2 a managerial one, and layer 1 an executive one.

## 4. The knowledge

| Node | Layer | Terminal | Files |
| --- | --- | --- | --- |
| N0 | 0 | no | 3 |
| N1 | 1 | no | 3 |
| N2 | 1 | no | 2 |
| N3 | 1 | yes | 1 |
| N4 | 2 | no | 5 |
| N5 | 2 | yes | 1 |
| N6 | 3 | no | 7 |

The 22 files are 20 documents (D01 to D20), one older version (D10 version 1) and one exact duplicate (the copy of D12). The documents are Markdown for now. In Phase 4 some become DOCX and PDF, and D19 becomes an image-only PDF so the vision model has something to read.

The case study plants these problems, each tied to a question in `case_study/answer_key.csv`:

| Problem | Where | What it will test |
|---|---|---|
| Exact duplicate | D12 and its copy | Duplicate detection |
| New version | D10 version 1 (120 buses) and version 2 (135 buses) | Versioning and the active version |
| Contradiction | D11 says Route 12 is busiest, D16 says Route 7 | Honest answers and research gaps |
| Scanned document | D19 | Reading text from an image |
| Node boundary | D07 belongs to N2, and Q22 asks N6 about it | Node isolation |
| Terminal nodes | N3 and N5 | The black-box boundary |
| Unanswerable | Q23 and Q24 | Saying "insufficient knowledge" |

There are 7 issues (`case_study/issues.csv`, three of them sub-issues of I01) and 6 people who can solve them (`case_study/people.csv`).

## 5. Objectives and scope

The proposal's 20 objectives are grouped into 8: cited answers (O1), knowledge lifecycle (O2), organization model (O3), issues (O4), projects and gaps (O5), transfer and judge (O6), engineering foundations (O7), and RFP (O8). RFP generation is a core objective built last, in Phase 13. The details, the scope in and out, the assumptions, the risks and the coverage map are in `scope/scope_and_objectives.md`.

## 6. The shared vocabulary

The glossary in `glossary/glossary.md` gives each of 61 terms one meaning, the words to avoid, and a code name, across the proposal's 10 bounded contexts. Two examples show why it matters. A node's subject area is always called "field of activity", never "domain", because "domain" already means the whole problem area in domain-driven design. And "project proposal" always means the document, while "RFP response" means the entity that answers an RFP.

## 7. How success is judged

The metrics are in `metrics/metrics.md` and `metrics/metrics.csv`. Each of the 8 objectives has at least one metric, every question type has a grading rule, and the rules that must always hold are listed as hard rules in `metrics/hard_rules.csv`. The order is fixed: measure the baseline in Phase 2, then agree the targets with the supervisor. The checker refuses a target without a recorded source.

## 8. How the work is tested

The testing rules are in `docs/unit_testing_rules.md`. In one sentence: a unit test checks our rules and must give the same result everywhere, while an evaluation measures the models and is reported as a metric. Models are replaced by test doubles in unit tests, and the network is blocked to prove the system works offline.

## 9. Risks and assumptions

| Risk or assumption | What we do about it |
|---|---|
| Small local models answer worse than large ones | Measure them in Phase 2 on the answer key before any design depends on them |
| The laptop has a 4 GB GPU, so only small models run well | Phase 2 chooses models that fit, and records speed and memory as metrics |
| The case study is small (26 questions, one duplicate pair) | Read differences of one question as noise, and add planted cases before trusting a metric |
| A judge model is inconsistent and biased | Check it against human scores (M18 to M20) before using its scores to accept or reject |
| The proposal is in Persian and the project is English only for now | Keep model choices that also support Persian where possible, and test Persian in a later phase |
| Terms or numbers drift apart between files | `python tools/run_checks.py` compares the Markdown pages with the CSV files |

## 10. Decisions to confirm with the supervisor

- The metric targets, once the baseline exists, and the way they are agreed.
- The judge threshold of 18 out of 20, which is the proposal's default.
- The registry template and the term "terminal node".
- The 28 metrics and the choice of key-fact grading for the baseline.
- The testing standard: pytest, three markers, and metrics for model quality.
- The open choices listed under "Decisions to confirm" in the glossary.

## 11. Deliverables

| Deliverable of the proposal | File | Status |
| --- | --- | --- |
| Domain discovery report | `docs/domain_discovery_report.md` | draft, this file |
| Initial glossary | `glossary/glossary.md` | done, to confirm |
| Node and layer registry template | `registry/node_layer_registry.csv` | done, to confirm |
| Baseline of evaluation metrics | `metrics/metrics.md` | metrics defined, baseline values come from Phase 2 |

| Step of Phase 1 | Status |
| --- | --- |
| 1. Define the objectives and scope | done |
| 2. Create the shared vocabulary | done |
| 3. Collect initial sample documents | done (the city case study) |
| 4. Identify the first layers and nodes | done (the registry, 7 nodes) |
| 5. Define the first evaluation metrics | defined, targets wait for the supervisor |
| 6. Decide the unit-testing method | done, in `docs/unit_testing_rules.md` |

## 12. Hand-off to the model baseline

Phase 2 needs three things from this phase: the answer key and `metrics/key_facts.csv` to grade model answers, the metrics that Phase 2 measures (M01 to M04, M06 to M09, M12 to M14, M20 and M22 to M25), and the testing rules for the code it writes. It returns the baseline values and the model registry.
