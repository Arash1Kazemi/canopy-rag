# Team plan

We are four. The lead keeps building the core (Part 3). Each teammate gets one task that is useful now, can be done without the lead's help, and teaches one part of the project.

## The working rule

- Each teammate writes only in their own folder: `team/<name>/`.
- The lead copies finished work into the project, then runs `tools/run_checks.py` and the tests.
- So nobody can break the project by accident, and every change has been checked once.

## Week 0: everyone reads (about 2 hours)

1. `docs/project_explained.html`: open it in a browser and click through.
2. `diagrams/view_in_browser.html`: the four diagrams (the city, a question's journey, how we measure, roadmap and team).
3. `glossary/glossary.md`: use these words and no others.
4. Then the reading for your own task, listed below.

## The lead: review Parts 3 to 6, then Part 7

- **Done:** the Part 3 design (`architecture/architecture.md`, `architecture/domain_model.md`, `architecture/unit_test_plan.md`), the Part 4 ingestion prototype (`architecture/ingestion.md`, code in `rag_core/`), Part 5 (`architecture/versioning_and_duplicates.md`: change summary, chunk life cycle, duplicate detection) and Part 6 (`architecture/hierarchy_and_layers.md`: layer registry, node and layer workflows, moving a node).
- **Now:** read the design and the code until you can explain every decision in `architecture/architecture.md` section 10; take the "to confirm" decisions to the supervisor; then start Part 7 (issue and sub-issue modelling).
- **Also:** merges teammates' work, answers their questions, and runs the checks.

## Teammate A: unseen questions

- **Why it matters:** the 26 questions were used to choose the setup, so they flatter it. Someone who never saw the prompts writes a fair test.
- **Read:** `case_study/` (the documents and the answer key format), `study_notes/01_metrics.md`, `metrics/key_facts.csv`.
- **Do not read:** `prompts/`. Not seeing them is the point of the task.
- **Task:** write 10 new questions in `team/A/unseen_questions.csv` with the same columns as the answer key, plus their key facts. Cover each type: a plain fact, a version, a conflict, a terminal node, and an unanswerable question.
- **Done when:** each question names its node, its sources and its key facts, and a second person can find each answer in the documents.

## Teammate B: model runs

- **Why it matters:** three runs are still open from Part 2, and a second laptop shows whether the operator guide really works.
- **Read:** `docs/operator_guide.md`, `docs/how_to_use_the_models.md`, `study_notes/06_running_and_limits.md`.
- **Task:**
  1. Pull `qwen3:4b-instruct` and rerun E2, E3, E5 and E6.
  2. Run one experiment with Wi-Fi off.
  3. Rerun E6 with `$env:OLLAMA_EXE` set, so `ollama ps` (the GPU and CPU split) is recorded.
- **On your own laptop:** the scripts take paths as parameters (`start_ollama.ps1 -OllamaDir ... -ModelsDir ...`). Write down your hardware, because speed and memory results depend on it.
- **Done when:** the result folders are in `team/B/results/`, and `team/B/notes.md` lists every step where the guide was unclear.

## Teammate C: test the ingestion prototype on real files

- **Why it matters:** the prototype reads DOCX with the standard library and has adapters for PDF, scanned PDF and DOC, but it was tested only on files made by our own code. Files saved by Word or LibreOffice are messier (styles, tables, page breaks). Only real files show whether the adapters hold.
- **Read:** `architecture/ingestion.md`, `architecture/metadata_schema.md`, `study_notes/08_architecture_and_ingestion.md`.
- **Task:**
  1. In Word or LibreOffice, save five case-study documents as DOCX and as PDF, and two as old DOC, in `team/C/files/<node folder>/` with the same file names (only the extension changes).
  2. Make the image-only D19 PDF, as `architecture/ingestion.md` describes.
  3. Install the tools on your laptop: `pip install pypdf pypdfium2`, and LibreOffice. Check with `python -m rag_core extractors`.
  4. Ingest each set into its own run: `--documents team/C/files --suffix .docx`, then `.pdf`, then `.doc`, and D19 with `--ocr`.
  5. For each file, compare the extracted text in `chunks.csv` with the Markdown original. Write what was lost or changed.
  6. For PDF, compare pypdf with one other offline library on the same files, with a documentation link for every claim.
- **Done when:** `team/C/ingestion_test.md` has one row per file (format, outcome, what was lost), and every problem found has a short example.

## Every week

- One short meeting: each person shows what they finished and where they are stuck.
- A task is finished only when its "done when" line is true.
