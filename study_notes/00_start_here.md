# Study notes: start here

These notes explain every step of the project so far in plain words. Each note follows the same pattern: the idea in one minute, an analogy, the precise idea, a simple example, a realistic example from the city, a short snippet, the common mistake, and questions with answers at the end. Math is explained in words first.

Read them in order. Each one says which book chapter it connects to. The book is "AI Engineering" by Chip Huyen. It was written in 2024, so its examples of models are old, while its methods still hold. A note says so wherever that matters.

## The map

| Note | Topic | Book chapters | What you can do after it |
| --- | --- | --- | --- |
| `study_notes/01_metrics.md` | define the first evaluation metrics | 3, 4, 6 | Explain how an answer is graded, what precision and recall are, and why a target waits for a baseline |
| `study_notes/02_unit_testing.md` | decide the unit-testing method | 3, 4 (the boundary only) | Write a pytest test with a test double, and say what must not be unit-tested |
| `study_notes/03_domain_discovery_report.md` | the domain discovery report | none (domain-driven design) | Present Phase 1 to your supervisor in five minutes |
| `study_notes/04_model_review.md` | review the candidate models | 2, 4, 7 | Read a model card, estimate if a model fits your laptop, and justify the short list |
| `study_notes/05_registry_and_prompts.md` | model registry and prompts | 5 | Explain why prompts are files, why they are versioned, and why embedding models need prefixes |
| `study_notes/06_running_and_limits.md` | run the models, test prompts, find the limits | 2, 3, 4 | Run the experiments, read their results, and say what they do not prove |
| `study_notes/07_reading_the_baseline.md` | reading the results | 2, 3, 4 | Read a result critically: check the answers, fix grading honestly, compare E2 with E3 |
| `study_notes/08_architecture_and_ingestion.md` | the architecture (Phase 3) and ingestion (Phase 4) | 6, 8 (and domain-driven design) | Say which object owns which rule, why the domain imports nothing outside, and how a file becomes cited chunks |
| `study_notes/09_versions_and_duplicates.md` | versions, the chunk life cycle and duplicates (Phase 5) | 6, 8 | Explain the change summary, why "retired" is not a chunk stage, and resemblance versus containment |
| `study_notes/10_nodes_layers_and_rules.md` | nodes, layers and the layer registry (Phase 6) | domain modelling | Say why a layer's rule belongs to the receiving layer, what moving a node does, and the two halves of H10 |

The final report of Phases 1 and 2 is `docs/final_report.md`, and the Phase 2 numbers are in `docs/baseline_report.md`. The design of Phases 3 and 4 is in `architecture/README.md`.

## How the pieces fit

```
answer key (26 questions)  ->  key facts + grading rules  ->  metrics (28)  ->  baseline (Phase 2)  ->  targets (supervisor)
                                                  ^
                                      hard rules (10) are tested, not measured
```

## Checking your own work

`python tools/run_checks.py` checks the data and the pages. `python -m pytest` (from `UNI-Project/`) checks the code. Neither one checks the models: that is what the experiments do.
