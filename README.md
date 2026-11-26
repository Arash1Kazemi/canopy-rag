# AI Engineering: Offline Hierarchical RAG Project

## Run with Docker and SQLite

Run these commands from `UNI-Project` with Docker Desktop running.

```powershell
docker build --target test -t uni-project:test .
docker build -t uni-project .
docker run --rm --network none -v uni-project-data:/data uni-project migrate-db
docker run --rm --network none -v uni-project-data:/data uni-project ingest-case-study
docker run --rm --network none -v uni-project-data:/data uni-project show-hierarchy
```

The test target runs the validators and the default pytest suite inside the image.
The volume keeps `/data/project.sqlite` after a container exits. The image build
downloads dependencies, and the commands above run offline after the build.
For legacy `.doc` input, build the LibreOffice variant with
`docker build --target with-doc -t uni-project:with-doc .`.
Scanned-document OCR requires a reachable local Ollama instance.

Outside Docker, `python -m rag_core migrate-db` creates `data/project.sqlite`.
Set `RAG_DATA_DB` to choose a different file. A first run also imports the CSV
datasets automatically. The import runs once per database, so later runs preserve
database edits. The `nodes` and `layers` tables hold the live hierarchy.
Tables such as `case_study_answer_key` hold imported datasets. The registry
dataset tables preserve the original seed rows.

Default ingestion writes items, versions, and chunks to the same database.
`--out` or `--run-id` creates an isolated ingestion database as before.
Use `--hierarchy-db` with ingestion to use a previously created hierarchy database.
The original CSVs serve as seed inputs and validator fixtures. Generated CSVs
are reports, and the original documents remain available for re-ingestion.

One project, one place. Everything lives in this folder, `UNI-Project`.

```
project/                                # this folder, named UNI-Project on disk
├── CLAUDE.md                           # tutor role, decisions and rules; Claude Code loads it when a session starts here
├── README.md
├── pytest.ini                          # test settings (pytest)
├── source/                             # the project proposal (Persian), the source of truth
├── docs/                               # reports and guides: final_report, domain_discovery_report, baseline_report,
│                                       #   model_review, prompt_test_plan, unit_testing_rules, how_to_use_the_models, operator_guide
├── study_notes/                        # a full explanation of every step, in plain words; start with 00_start_here.md
├── case_study/                         # the city: documents, issues, people, answer key
├── registry/                           # the node and layer registry, and what each column means
├── scope/                              # objectives, scope, assumptions, risks, the proposal's 20 objectives mapped to 8
├── glossary/                           # 109 terms in 8 areas, with avoid-words and code names
├── metrics/                            # 28 metrics, grading rules, key facts, 10 hard rules
├── models/                             # model_registry.csv: the models, their sources and what our runs showed
├── prompts/                            # versioned prompt templates and prompt_registry.csv
├── experiments/                        # experiments.csv and judge_probe.csv
├── architecture/                       # Phase 3 and 4 design: architecture, domain model, test plan, ingestion, metadata, chunking, citations
├── rag_core/                           # the core (Phase 3 on): domain, ports, ingestion, rag, infrastructure; python -m rag_core ... index | ask | evaluate
├── baseline_runner/                    # the Phase 2 experiment runner: client, chunking, retrieval, grading, experiments
├── diagrams/                           # four draw.io diagrams and view_in_browser.html
├── site/                               # the team hub blueprint (index.html)
├── config/                             # settings that are data (issue_progress_weights.csv, untuned)
├── data/                               # project.sqlite
├── tests/                              # unit tests (pytest): 743 pass, 2 deselected
├── scripts/                            # setup_ollama.ps1, start_ollama.ps1, render_d19.ps1, make_real_files.py, save_ollama_ps.py, duplicate_experiment.py
├── results/                            # one folder per run: experiments, and ingestion/ for the core
└── tools/
    └── run_checks.py                   # six validators; run before and after every change: python tools/run_checks.py
```

Status:

- The domain work is complete (scope, case study, vocabulary, registry, metrics, testing rules) and waits for the supervisor on the open decisions and the metric targets.
- The model baseline ran once (`docs/baseline_report.md`). Open: a rerun with `qwen3:4b-instruct`, the run with Wi-Fi off, and the supervisor's targets.
- Phases 3 (the DDD architecture), 4 (ingestion, now with real DOCX, text PDF and image-only PDF files), 5 (versions, the chunk life cycle, duplicate detection), 6 (nodes, layers, the node directory), 7 (issues: ten statuses, progress, same-node comparison, sub-issue suggestions) and 8 (retrieval and question answering: vector index, node-filtered retrieval, context budget, answers with checked citations; commands `index`, `ask`, `evaluate`) are built and wait for review: start at `architecture/README.md`. Decisions A1 to A51 are all "to confirm"; `docs/supervisor_questions.md` lists every open question.
- Held-out questions HQ01 to HQ10 (`case_study/heldout_questions.csv`) are kept for the end of Phase 14. Tuning never reads them.
- Open: run E3 (`words80` against `sections80`), M15 (sub-issue suggestions for I01) and the Phase 8 evaluation (`index`, `ask`, `evaluate --run-id phase8-core-p01`, then the optional P13 run), all prepared in the operator guide (parts D, E, F); add a `model_registry.csv` row for `qwen3:4b-instruct` after pulling it; `data/project.sqlite` is stale, so point `RAG_DATA_DB` at a fresh file to read the real files.
- In-depth study pages for becoming a senior AI engineer (RAG, evals, local models, engineering habits): open `guides/index.html`.

The team plan is `docs/team_plan.md`.
