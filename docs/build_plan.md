# Build plan: fix Phases 1 to 7, then build Phases 8 to 16

Written: 2026-11-25. Hand this file to a coding agent together with `docs/build_prompt.md`.

The source of truth is the project proposal, `source/technical-proposal-offline-hierarchical-rag-fa.md` (Persian). Section 21 lists the 16 phases. Sections 12 to 16 describe issues, IKE, status, RFP and the judge. If this plan and the proposal disagree, follow the proposal and write down the difference.

## 0. Where the project stands

| Phase | Name | State on 2026-11-25 |
|---|---|---|
| 1 | Domain discovery | done (case study, scope, glossary, registry, metrics) |
| 2 | Offline models and baseline | done (baseline ran on 2026-10-28) |
| 3 | DDD architecture | done |
| 4 | Document ingestion | done (Markdown only; real DOCX and PDF missing) |
| 5 | Versioning, chunking, duplicates | done (policy numbers untuned) |
| 6 | Nodes, layers, hierarchy | done |
| 7 | Issues and sub-issues | **started**: `rag_core/issues/` (model, CSV repository), 5 tests. Most of the phase is missing (Part A, 7) |
| 8 to 16 | | not started |

Facts checked on 2026-11-25: `tools/run_checks.py` passes 6 of 6. pytest gives 335 passed and 2 deselected. Project data was moved into `data/project.sqlite` (`rag_core/infrastructure/project_db.py`). `CLAUDE.md` and `AGENTS.md` still say 328 tests and do not mention Phase 7 or the SQLite move.

## 1. Rules for every step

1. Run the checks before and after each change: `../.venv/bin/python.exe -I tools/run_checks.py` and `../.venv/bin/python.exe -m pytest -q`, both from `UNI-Project/`. Both must pass at the end of each milestone.
2. Add each new term to `glossary/` before using it in code or docs. Update the "N terms in M areas" prose and the `EXPECTED` dict in `tools/run_checks.py`.
3. Keep the answer key (`case_study/answer_key.csv`, 26 questions) valid. Do not change the 26 questions.
4. Never put test-design notes inside a case-study document, because it would be indexed. Use the manifest or a README.
5. Never invent a metric target. Targets stay `to agree with supervisor`. A measured number is a **baseline** and needs a source (run id and date).
6. Do not decide anything that belongs to the supervisor. Make a working choice, add it as decision `A21`, `A22` and so on to `architecture/architecture.md` with "To confirm: yes", and carry on.
7. Offline only (H06). Code talks only to `127.0.0.1`. The Ollama server is on port **11500**. Do not download models or packages. If one is needed, add the step to `docs/operator_guide.md` and stop for the student to run it.
8. Layering: the domain imports nothing from outside the domain. `tests/test_core_architecture.py` must cover each new package.
9. Each use case takes its repositories, models and clock as arguments. Unit tests use fakes from `rag_core/fakes.py`. Tests never need a running model.
10. For every new module, write the in-memory and the SQLite adapter, and run the same tests against both.
11. CSV files are plain UTF-8, LF line endings, no BOM. English only.
12. One milestone is one commit, with a clear message. Never push.
13. After each phase, write `study_notes/NN_<topic>.md` in the style of the existing notes. Start it with "Where we are: Phase X. Book: chapter Y". Cover the intuition, the precise idea, one example and the common mistake. Explain math in words. The student is learning, so the notes matter as much as the code.
14. After each phase, update `CLAUDE.md`, `AGENTS.md` and `README.md`: the "What exists" list, the "What is still open" list and the test count.

## Part A: recheck and improve Phases 1 to 7

Do Part A first. Phase 8 depends on A4, A5 and A6.

### A0. Housekeeping (small)

- Update `CLAUDE.md` and `AGENTS.md`: the test count, Phase 7 started, data in `data/project.sqlite`, and the `phases/` folder. Keep the two files saying the same thing.
- In `architecture/architecture.md`, change Issue Management from "planned" to "Phase 7, in progress" and point it to `rag_core/issues/`.
- Decide what `docs/implementation_roadmap.md` (untracked) is for. This plan supersedes its Phase 7 and 8 sections. Add a line at its top that says so; do not delete it.

### A1. Phase 1 (domain)

- Add a **held-out question set**: about 10 new questions on the same city, in a separate new file such as case_study/heldout_questions.csv (new). It must not be read by any tuning step. It gives Phase 14 an honest final test (book Ch. 3–4: do not tune on your test set).
- Add the **planted near-duplicate and overlap pairs** that M10 and M11 need. Put them in a test fixture folder such as `tests/fixtures/duplicates/`, not in `case_study/documents/`, so that answers do not change. Label each pair in a CSV.
- Collect every open supervisor question into one new file, docs/supervisor_questions.md (new): metric targets, the 18-out-of-20 threshold, the registry template, "terminal node", A1–A20, and the glossary's "Decisions to confirm". Keep one line per question with a link. This is for the student to take to the meeting.

### A2. Phase 2 (baseline)

The agent cannot run models. Prepare these runs, and the student runs them:

- In `docs/operator_guide.md`, add exact steps for three things. First, the rerun with `qwen3:4b-instruct` as a separate, labelled run. Second, the offline run with Wi-Fi off. Third, recording `ollama ps` and `nvidia-smi` during a run.
- Add a small script that saves `ollama ps` output next to each run's results, so it is not forgotten.

### A3. Phase 3 (architecture)

- Extend `tests/test_core_architecture.py` so it also checks `rag_core/issues/` and every package added later.
- Add to `architecture/domain_model.md` any field that Phase 7 adds to `Issue`.

### A4. Phase 4 (ingestion)

- Make real files. Use LibreOffice (installed) to convert some Markdown documents to DOCX and PDF. D19 must become an **image-only PDF**: render its pages to images with `rag_core/ingestion/png.py` or pypdfium2, then build a PDF with no text layer. Write a script, scripts/make_real_files.py (new), so this can be repeated. Record which documents are now DOCX or PDF in the manifest.
- Mixed PDFs: if a page has no text layer, send that page to the vision model port. Do this per page, not per file. Unit-test it with a fake vision model.
- Check that citations still carry the page numbers for PDF documents.
- Prepare (not run) the E3 experiment that compares `words80` with `sections80`, and add its steps to the operator guide.

### A5. Phase 5 (versions and duplicates)

- Add tests that pin the two planted problems before retrieval exists. The D10 v2 chunks are active and the v1 chunks are not. The D12 copy produces no chunks.
- Run `scripts/duplicate_experiment.py` on the new labelled pairs from A1. Record the results as M10 and M11 **baselines**, not targets.

### A6. Phase 6 (hierarchy)

- Add a restart test: save a hierarchy in SQLite, open a new repository on the same file, and check that nodes, layers, terminal flags and rules are the same.
- Add a function that the issue and retrieval code will call to answer "does this node exist?" and "is it terminal?". Validate a node id through it, never by string.

### A7. Phase 7 (issues), finish it

Proposal sections 12 and 14. Book: Ch. 5 (prompts for suggestions). Gaps found in the current code:

| Gap | Current code | What to build |
|---|---|---|
| Statuses | 5 statuses | The proposal lists 10 sample statuses (14.1): new, analyzing, knowledge identified, executor identified, solution proposed, in progress, awaiting decision, solved, unsolved, archived. Use those, add them to the glossary, and define the allowed transitions. Map the old values when importing. |
| Metadata | title, description, status, parent | Add field of activity, priority, category, created date, a free metadata map, sibling position and dependencies ("blocked by"). |
| Progress (H07) | none | Add a `ProgressPercentage` computed by fixed rules from the factors in 14.1: sub-issues defined, supporting knowledge, executor mapped, solution proposed, sub-issues solved. Put the weights in a config file and mark them as an untuned decision. The same input must always give the same output (test it). |
| Node rules | not checked | The node must exist. A sub-issue must be in its parent's node. No cycles in parent or "blocked by" links. |
| Comparison | Jaccard on two saved issues, stopwords included | Compare a **draft** against the existing issues **in the same node only**. Return ranked candidates with a score and the shared words. Remove stopwords. Leave a slot for embedding similarity, which comes in Phase 8. Record labelled pairs before choosing any threshold. |
| Sub-issue workflow | none | `suggest` (LLM through the `LanguageModel` port, with a versioned prompt in `prompts/`) → the user accepts, edits or rejects → accepted ones are saved together in one transaction. Use a fake model in tests. |
| Relative position (12.3) | none | Order siblings by position, and expose parent/child, dependency and same-category links. |
| Storage | CSV only | `SqliteIssueRepository` plus in-memory; import the 7 seed issues without changing ids, parents or meaning. |
| CLI | none | `create-issue`, `show-issue`, `list-issues --node`, `compare-issue`, `suggest-sub-issues`. |

Done when: the 7 issues load, a new N6 issue survives a restart, a draft about Route 7 crowding ranks I01 first, an issue from another node is never compared, H07 has tests, and M15 has a way to be measured (save the suggestions for I01 so a human can match them against I02–I04).

## Part B: build Phases 8 to 16

Each phase: deliverables from proposal section 21, the milestones, a "done when" check, and the metrics and hard rules it touches.

### Phase 8: RAG retrieval and question answering (Book Ch. 6, and Ch. 5 for the prompt)

1. **8A Embed and index.** Connect the `EmbeddingModel` port to Ollama (qwen3-embedding-0.6b, the baseline). Add a `VectorIndex` interface with an exact-search adapter (the corpus is small). Store the chunk id, version, node, model tag and chunking policy with each vector. Rebuild when the model or the policy changes. Chunks move to the `indexed` stage (A12).
2. **8B Retrieve.** Filter by node, active version and metadata **before** ranking (H01). Return chunk ids, scores and locations.
3. **8C Answer.** Assemble the context within the model's limit, use `prompts/answer_with_citations_v1.txt` or a v2, and validate every citation against the chunks that were actually given (H09). Return `insufficient knowledge` when there is no evidence.
4. **8D Evaluate.** `python -m rag_core ask` and `evaluate`. Run the 26 questions with the same settings as the baseline and compare M01–M09 and M22–M24 with the Phase 2 run. Then move `baseline_runner` to call the core (architecture section 9).

Done when: a foreign-node chunk with the best score never appears (test), Q22 is refused, D10 gives 135 buses, the Q06 answer names both routes, and the evaluation report is in `results/` and `docs/`. The real model run is done by the student; the agent prepares the command.

### Phase 9: executors and IKE (Proposal 13)

- `Executor` aggregate from `case_study/people.csv`: expertise tags, role, past projects, documents written, and availability when it is given.
- Match an issue to executors with an explainable score (which tags matched). Ranks must be deterministic.
- IKE model: the 12 typed relations of proposal 13.1 as an edge list with a type, a source and a target, stored in SQLite.
- A relation summary for one node (text and CSV), which becomes knowledge that can be sent up later (13.3).
- Prepare the M15 and M16 human rubrics as files.

### Phase 10: LLM as a judge (Proposal 16; Book Ch. 3 and 4)

- A rubric model (criteria, points, total out of 20), versioned judge prompts, and a strict score parser. A parse failure is a failed judgment, never a pass.
- A threshold of **18 out of 20** (decided), stored per layer so that the supervisor can change it.
- Run the judge twice for repeatability (M20) and record both runs.
- Unit tests use a stub judge. They check the parser, the threshold edge cases (17, 18, 19) and bad output.

### Phase 11: node cycles and upward transfer (Proposal 9 and 10)

- A cycle triggered on request, which reads domain events since the last package (architecture section 8).
- The `TransferPackage` aggregate: the detail level comes from the parent layer's `TransferRule` (A16). It is judged, and it is **never sent** below the threshold (H05). That is a unit test with a stub judge.
- AI suggestions to improve a package, saved as suggestions only.
- The latest accepted package per node and period is stored in SQLite and exported as CSV.
- Prepare M18, M19 and M21: an export of about 20 packages and a form for human scores.

### Phase 12: projects, research, achievements and gaps (Proposal 11 and 14.2–14.3)

- Project records (research, achievement, challenge, unsolved issue), linked to knowledge, issues and executors.
- Research-gap rules from 14.3: no knowledge, old knowledge, conflict, low confidence, no executor, an open challenge, or a judge score below the threshold. The case study must flag the Q06 conflict and the Q23 missing budget (M17).
- Key-issue ranking from the 14.2 factors, deterministic (H08). The weights are config and marked "to confirm".

### Phase 13: RFP and RFP responses (Proposal 15)

- Draft an RFP from an unsolved issue and its node knowledge, with cited sections. The I06 case gives M27. Write the list of required sections first and mark it "to confirm".
- Register an RFP response, evaluate it with a rubric, and generate feedback where each point names an RFP criterion (M28).
- Link the RFP and responses back to the node's knowledge. Keep the class names `RFP` and `Proposal` (glossary).

### Phase 14: prompt testing, model tuning, sample-set evaluation (Book Ch. 3, 4, 5)

- Compare prompt versions and retrieval settings (k, chunking) on the 26 questions. Run **once** on the held-out set at the end.
- Compare local models per task with the registry in `models/`.
- Refine the judge rubrics and the transfer detail rules.
- Write docs/evaluation_report.md (new) with baselines and sources. Leave targets empty.

### Phase 15: unit-test completion and hardening

- Make sure every test area in `docs/unit_testing_rules.md` has a passing test (M26). Compute M26.
- Cover every H01–H10 with a named test, plus a network-blocked test of the whole pipeline with fakes.
- Write docs/unit_test_report.md (new) and a final checklist.

### Phase 16: final documentation and presentation

- Final technical docs, an operator guide for each main workflow, and a demo script that runs the city end to end (ingest → ask → issue → judge → transfer → RFP).
- docs/project_summary_report.md (new) that gathers the evidence, and a final study note for each phase.

## What the agent must NOT do

- Set targets, change the judge threshold, or answer supervisor questions.
- Download models or run anything that needs the network.
- Edit `_superseded/`, the proposal, or the 26 questions in the answer key.
- Claim a model result it did not see. If a run needs Ollama, say "prepared, not run".
