# AI Engineering: Offline Hierarchical RAG Project

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
├── glossary/                           # 61 terms in 8 areas, with avoid-words and code names
├── metrics/                            # 28 metrics, grading rules, key facts, 10 hard rules
├── models/                             # model_registry.csv: the models, their sources and what our runs showed
├── prompts/                            # versioned prompt templates and prompt_registry.csv
├── experiments/                        # experiments.csv and judge_probe.csv
├── architecture/                       # Phase 3 and 4 design: architecture, domain model, test plan, ingestion, metadata, chunking, citations
├── rag_core/                           # the core (Phase 3 on): domain, ports, ingestion, infrastructure; python -m rag_core
├── baseline_runner/                    # the Phase 2 experiment runner: client, chunking, retrieval, grading, experiments
├── diagrams/                           # four draw.io diagrams and view_in_browser.html
├── site/                               # the team hub blueprint (index.html)
├── tests/                              # unit tests (pytest)
├── scripts/                            # setup_ollama.ps1, start_ollama.ps1, render_d19.ps1
├── results/                            # one folder per run: experiments, and ingestion/ for the core
└── tools/
    └── run_checks.py                   # six validators; run before and after every change: python tools/run_checks.py
```

Status:

- The domain work is complete (scope, case study, vocabulary, registry, metrics, testing rules) and waits for the supervisor on the open decisions and the metric targets.
- The model baseline ran once (`docs/baseline_report.md`). Open: a rerun with `qwen3:4b-instruct`, the run with Wi-Fi off, and the supervisor's targets.
- Phases 3 (the DDD architecture), 4 (the ingestion prototype), 5 (versions, the chunk life cycle, duplicate detection) and 6 (nodes, layers, the layer registry) are built and wait for review: start at `architecture/README.md`. PDF, scanned PDF and DOC reading wait for tools to be installed (`architecture/ingestion.md`).
- In-depth study pages for becoming a senior AI engineer (RAG, evals, local models, engineering habits): open `guides/index.html`.

The team plan is `docs/team_plan.md`.
