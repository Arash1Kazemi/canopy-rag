# Final report

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Source: the project proposal (`source/technical-proposal-offline-hierarchical-rag-fa.md`), and the files of both phases. Status: for supervisor review. Date: 2026-10-28.

## In one paragraph

Phase 1 fixed what the system is for, the test organization (the City: 7 nodes, 20 documents, 26 questions with planted problems), the shared vocabulary (45 terms), and how success is measured (28 metrics, 10 hard rules, and grading rules for every question type). Phase 2 chose small local models that fit a 4 GB laptop GPU, built a runner that asks the 26 questions and grades the answers, and measured a first baseline fully offline. The baseline setup (`qwen3-embedding:0.6b` with `phi4-mini:3.8b`, and `glm-ocr` for scans) answers 21 of 23 answerable questions correctly, refuses all 3 that it should, never uses another node's documents, and takes under a second per question. It fails the two problems that later phases are meant to solve: reporting a contradiction, and citing a duplicate once.

## Domain discovery

| Step of the proposal | Result | File |
|---|---|---|
| 1. Objectives and scope | 20 proposal objectives grouped into 8, with scope, risks and checks | `scope/scope_and_objectives.md` |
| 2. Shared vocabulary | 45 terms with one meaning each | `glossary/glossary.md` |
| 3. Sample documents | The city case study | `case_study/README.md` |
| 4. Layers and nodes | The registry template, 7 nodes in 4 layers | `registry/node_layer_registry.csv` |
| 5. Evaluation metrics | 28 metrics, 5 grading rules, 10 hard rules, baselines from Phase 2, no targets yet | `metrics/metrics.md` |
| 6. Unit-testing method | pytest, test doubles, 14 test areas | `docs/unit_testing_rules.md` |
| Report | All of the above in one story | `docs/domain_discovery_report.md` |

## Offline models and the technical baseline

| Step of the proposal | Result | File |
|---|---|---|
| 1. Review candidate models | 17 models reviewed with sources, 7 downloaded | `docs/model_review.md` |
| 2. Run models locally | Standalone Ollama on this laptop, port 11500, checksum checked | `docs/how_to_use_the_models.md` |
| 3. Prompt experiments | 11 versioned prompts, 6 experiments | `docs/prompt_test_plan.md` |
| 4. Limits of offline models | Measured in E2 to E6 | `docs/baseline_report.md` |
| 5. Model registry structure | 19 columns, rules, results noted per model | `docs/model_registry_structure.md` |

The three deliverables of Phase 2 are the baseline report, the method for using the models, and the prompt test plan. The operator guide (`docs/operator_guide.md`) is the runbook.

## The baseline in numbers

| Metric | Baseline |
|---|---|
| Retrieval: answer-key source in the top 3 chunks (M06, M08) | 1.00 |
| Answer correctness with real retrieval (M01) | 0.91 (21 of 23) |
| Citation validity (M02) | 0.87 |
| Correct refusal (M03) | 1.00 (3 of 3) |
| False refusal (M04) | 0.00 |
| Version handling (M09) | 1.00 |
| Duplicate cited once (M12) | 0.00 |
| Scanned page read (M13) | 1.00 |
| Judge repeatability on the probe (M20) | 1.00 |
| Question latency (M24) | 0.70 s median, 1.52 s at the 90th percentile |
| GPU memory in use (M25) | 3255 MB of 4096 MB |
| Hard rule H01, node isolation | held: 0 violations |

## What we learned

1. **A small model is enough for grounded answers on this data.** `phi4-mini` got 22 of 23 right when given the right files, and 21 of 23 with real retrieval. Its weak points are reporting a conflict and always citing.
2. **The planted problems are real problems.** With both copies of the shift rules in the index, the model cites both. Asked about a contradiction, it picks one side. That is the case for duplicate detection and research-gap flagging in later phases.
3. **Grading rules need a human pass.** Four rules were too strict and moved the main metric from 0.74 to 0.91. Both numbers are reported.
4. **A model tag can hide a different model.** `qwen3:4b` is a thinking-only version, which makes its results not comparable. Read `/api/show` before running a model.
5. **Specialised beats general for reading pages, at a cost.** The 0.9B OCR model read every page exactly but took about a minute. The 2B general model was fast but stopped early once.

## Status of the hard rules

| Rule | Status |
|---|---|
| H01 node isolation | Tested in code and held in the real runs |
| H02 registry rules, H10 terminal nodes | Checked by `run_checks.py` |
| H06 offline | Tested in code (the network is blocked in unit tests). The run with Wi-Fi off is still to do |
| H03, H04, H05, H07, H08, H09 | Belong to later phases, where their code is built |

## How the work was checked

- `python tools/run_checks.py`: 6 validators over the data and the pages, all pass. The checker itself was proven by breaking a copy in 60 ways.
- `python -m pytest` from the project folder: 64 unit tests pass.
- Every failed answer of the baseline was read by a human.

## Decisions for the supervisor

1. The targets for the 16 metrics that now have a baseline.
2. Whether the baseline setup (`qwen3-embedding:0.6b`, `phi4-mini`, `glm-ocr`) is the starting point for Phase 3.
3. The judge threshold of 18 out of 20, and whether a small local judge is acceptable after the Phase 11 check.
4. The open choices of Phase 1: the registry template, the term "terminal node", and the glossary's "Decisions to confirm".

## Open work before Phase 3

1. Rerun with `qwen3:4b-instruct`, to have a fair second LLM.
2. The offline run with Wi-Fi off.
3. Record the GPU and CPU split (`ollama ps`).
4. New, unseen questions to check the setup without the bias of tuning.
