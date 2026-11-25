# Prompt for the build agent

Copy everything below the line into Claude Code, opened in the `UNI-Project/` folder.

---

You are building the rest of my university project, an offline hierarchical RAG core. It runs on small local models and has no internet.

**Read these first, in this order:**

1. `CLAUDE.md`, for the project rules and the decisions already made.
2. `docs/build_plan.md`, which is your plan. Follow it in order: Part A (fix Phases 1 to 7), then Part B (Phases 8 to 16).
3. `architecture/architecture.md` and `architecture/domain_model.md`, for the design you must follow.
4. `source/technical-proposal-offline-hierarchical-rag-fa.md`, the source of truth. It is in Persian; read the sections that the plan names for each phase.

**How to work:**

- Work one milestone at a time. Before each milestone, run the checks and the tests:
  - `../.venv/bin/python.exe -I tools/run_checks.py`
  - `../.venv/bin/python.exe -m pytest -q`
  Run them again after the milestone. Both must pass before you commit. One milestone is one commit. Never push.
- Write tests first for each rule (H01 to H10 in `metrics/hard_rules.csv`). Tests use the fakes in `rag_core/fakes.py` and never need a running model.
- Keep the layering: the domain imports nothing from outside the domain. Inject repositories, models and the clock.
- Add a new term to the glossary before you use it, and update the counts that `tools/run_checks.py` checks.
- Run offline only. Ollama is on `127.0.0.1:11500`. Do not download anything. If a step needs a model run or a download, prepare the command, add it to `docs/operator_guide.md`, mark the result "prepared, not run", and continue with the next step that does not need it.
- Never invent a metric target, a threshold or a supervisor decision. When you must choose, add a decision `A21`, `A22` and so on to `architecture/architecture.md` with "To confirm: yes", and keep going.
- Never write test-design notes inside `case_study/documents/`. Never change the 26 questions in the answer key. Do not touch `_superseded/`.

**I am learning, so for each phase also:**

- Write `study_notes/NN_<topic>.md` in the style of the existing notes. Start it with "Where we are: Phase X. Book: chapter Y" (Chip Huyen's "AI Engineering"). Cover the intuition, the precise idea, one example and the common mistake. Explain math in words, and use short sentences.
- Update `CLAUDE.md`, `AGENTS.md` and `README.md` (what exists, what is still open, the test count).

**At the end of each phase, stop and report in a short message:**

1. What you built (files and commands).
2. The test count and the checks result.
3. The decisions you marked "to confirm".
4. What I must run myself (model runs, downloads).
5. Anything in the plan you skipped, and why.

Then wait for me to say "continue". Start with Part A, step A0.
