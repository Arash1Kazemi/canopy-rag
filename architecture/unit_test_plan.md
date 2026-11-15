# Unit-test plan

Project: offline hierarchical RAG core. Source: Phase 3 of the project proposal (section 18) and `docs/unit_testing_rules.md`. Status: draft for supervisor review. Date: 2026-11-01.

This is the third Phase 3 deliverable. `docs/unit_testing_rules.md` says how we test. This page says what is tested, in which file, and in which phase the rest comes.

## Structure

- All tests are in `tests/`. Phase 2 tests are named after their module (`test_grading.py`). Core tests start with `test_core_` so the two sets never share a file name.
- Shared test doubles of the core are in `rag_core/fakes.py` and tested in `tests/test_core_fakes.py`. Small object builders are in `tests/core_builders.py`.
- The network is blocked in every unit test by `tests/conftest.py` (H06).
- `python -m pytest` from `UNI-Project/` runs everything except the `integration` and `evaluation` markers.

## Test areas and files

| Area | Hard rules | Test files | State |
| --- | --- | --- | --- |
| Registry and layers | H02, H10 | `test_core_organization.py`, `test_core_hierarchy.py`, `test_core_layer_registry.py`, `test_core_workflows.py` | done |
| Node isolation | H01 | `test_retrieval.py` (Phase 2), `test_core_ingestion.py` (every chunk carries its node; `active_chunks` filters) | done for now; the retrieval service tests come in Phase 8 |
| Versioning | H03, H04 | `test_core_knowledge.py`, `test_core_storage.py`, `test_core_ingestion.py`, `test_core_metadata.py`, `test_core_changes.py`, `test_core_lifecycle.py` | done |
| Duplicates and overlaps | none | `test_core_duplicates.py` (exact, near, overlap; the City has no findings), `test_core_ingestion.py` (an exact repeat is skipped) | done; similarity by embeddings comes in Phase 8 |
| Chunking | none | `test_core_chunking.py` (also proves `words80` equals the Phase 2 chunks) | done |
| Retrieval | none | `test_retrieval.py` | Phase 2 code; Phase 8 adds the core version |
| Answers and citations | H09 | `test_grading.py`, `test_core_citation.py` | citations done; the formatter comes in Phase 8 |
| Grading rules | none | `test_grading.py` | done (Phase 2) |
| Issues | H07 | none yet | Phase 7 |
| Priorities and gaps | H08 | none yet | Phase 12 |
| Transfer and judge decision | H05 | none yet | Phases 10 and 11 |
| Prompt templates | none | `test_prompts.py` | done (Phase 2) |
| Offline guard | H06 | `conftest.py`, `test_ollama_api.py` | done |
| RFP | none | none yet | Phase 13 |

Three files test the design itself rather than one area:

| File | What it proves |
| --- | --- |
| `test_core_architecture.py` | the domain never imports an outer layer, a database, a process or the network |
| `test_core_extractors.py` | format detection and every extraction adapter, with doubles for pypdf, the page renderer, the LVM and LibreOffice |
| `test_core_fakes.py` | the core's test doubles behave as their tests expect |

## Which double for which part

| Real part | Double | Kind |
| --- | --- | --- |
| The clock | `FixedClock` | stub |
| The LVM (glm-ocr through Ollama) | `StubVisionModel` | stub and spy |
| pypdf | `stub_pdf_reader` | stub |
| The page renderer (pypdfium2) | `stub_page_renderer` | stub |
| LibreOffice | `SpyRunner` | spy |
| SQLite | `InMemoryKnowledgeRepository`, and the same tests run on a temporary SQLite file | fake |

One test needs a real library and is skipped without it: `test_a_real_pdf_text_layer_is_read_by_pypdf` runs when pypdf is installed.

## Proof that the tests catch bugs

On 2026-11-01 three rules were broken on purpose, one at a time, and each was caught by a failing test: the H10 check in ingestion, the H04 check in `KnowledgeItem.add_version`, and the H02 layer check in `Hierarchy.add_node`. The code was then restored and all tests passed. Run the same experiment after a big change.

On 2026-11-08 eleven rules of Phase 5 were broken on purpose, one at a time, and ten were caught by a failing test: versions of one item compared, an exact duplicate never found, a shared phrase counted as an overlap, overlap checked before near, every version compared by default, a chunk allowed to skip a stage, a chunk that is not indexed treated as retrievable, an inactive version treated as retrievable, no change summary at ingestion, and the detector's notes dropped. The one not caught is turning difflib's `autojunk` shortcut on: no test can tell the two settings apart (`rag_core/knowledge/changes.py` says so).

On 2026-11-08 seventeen rules of Phase 6 were broken in the code and six in `registry/layer_registry.csv`, one at a time, and every one was caught, by a failing test or by `tools/run_checks.py` for the file. They covered moving a node under itself, a descendant or a terminal node, moving the root, a move that does not shift layers or leaves the subtree behind, a move that keeps old reporting values, a terminal node with children or with two documents, editing a rule-owned value or an id, a node that ignores its layer's rule, a rule that is kept after it broke the registry, a hierarchy that disagrees with its registry called complete, a rule that asks for more detail going up, a topic both required and excluded, foreign keys off, and an inconsistent hierarchy saved.

## Counts on 2026-11-08

328 tests pass and 2 integration tests are deselected by default. 64 tests are from Phase 2; 264 are new core tests. Metric M26 (rule test coverage) counts the areas with at least one passing test: 11 of the 14 areas have one now; Issues, Priorities and gaps, Transfer and judge decision, and RFP wait for their phases.
