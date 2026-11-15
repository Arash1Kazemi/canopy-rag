# Note 5: the model registry and the prompts

Where we are: steps 5 (model registry structure) and 3 (prompt experiments, the prompt part). Book: chapter 5 (prompt engineering), chapter 2 (sampling and structured outputs).
Files made: `docs/model_registry_structure.md`, `prompts/prompt_registry.csv`, the prompt files in `prompts/`, `experiments/judge_probe.csv`.

## In one minute

A prompt is the text you send to a model. We keep every prompt in its own file, with blanks for the parts that change, and a version number in its name. A registry lists them, the way a model registry lists the models. This lets us repeat an experiment, compare two prompts fairly, and see exactly what changed between two results.

## 1. A prompt is a template

Analogy: a form letter. "Dear {{name}}, your order {{order}} has shipped." The wording is fixed, the blanks are filled for each customer.

Chapter 5 of the book says to keep prompts apart from code, and gives four reasons: reuse, testing (prompts and code can be tested separately), readability, and collaboration (a subject expert can improve a prompt without reading code). It also says to version prompts and to track experiments, and to evaluate each prompt in the context of the whole system, because a prompt can improve one step and hurt the whole.

Our rules:

- A prompt file is named `<what>_v<number>.txt`. Once used in a result, it is **never edited**. A change is a new file, `_v2`, and a new run. Both results are reported.
- Blanks are written `{{name}}`. The code refuses to render a prompt with a missing or an extra value. A half-empty prompt would give a bad answer without any error.

```python
Prompts().render("P01", context="[D13_maintenance_schedule_2025] ...", question="How many buses are overdue?")
```

## 2. The answer prompt, line by line

`prompts/answer_with_citations_v1.txt` (P01):

| Line | Why it is there |
|---|---|
| "Use only the documents below." | Groundedness: the model must not answer from memory. Without it a model may fill gaps with something that sounds right |
| "Cite the file in square brackets, for example [D10_bus_fleet_inventory_v2]." | Citations are an objective of the project, and the file stem is exactly what the grading rule checks (GR5) |
| "If the documents do not contain the answer, reply exactly: Insufficient knowledge." | A fixed phrase can be detected by code (GR2). It is also the objective's own wording |
| "Keep the answer short." | A short answer is faster and easier to grade |

What is not in it, on purpose: nothing about versions or duplicates. The baseline is the simplest version. We expect it to cite the old fleet inventory sometimes and to cite the shift rules twice. Those failures are the reason for the work of Phases 4 and 5.

## 3. Embedding models need prefixes

Analogy: a librarian who files pages and searches for pages. If the model was trained to see "search_document: ..." on pages and "search_query: ..." on questions, then giving it plain text puts both on the map in slightly different places than it expected, and the search gets worse.

| Model | Query | Document |
|---|---|---|
| `nomic-embed-text` | `search_query: <text>` | `search_document: <text>` |
| `embeddinggemma:300m` | `task: search result \| query: <text>` | `title: none \| text: <text>` |
| `qwen3-embedding:0.6b` | `Instruct: <task sentence>` then a new line, then `Query:<text>` | plain text |
| `bge-m3` | plain text | plain text |

These come from the model cards, not from the Ollama pages, and one test (`test_prefixes_match_the_model_cards`) fixes them. The common mistake is to embed everything with plain text and then conclude that the model is weak.

## 4. Prompts that ask for JSON

The judge probe (P04) asks the model to reply with one line of JSON: `{"verdict": "correct" or "wrong", "reason": "..."}`. Chapter 2 covers structured outputs: models can be asked for JSON, and the server can enforce it (`format: json`). Even then, parse defensively. Our `parse_verdict` accepts the JSON, falls back to finding `verdict: correct` in loose text, and returns `unparsed` if neither works. An unparsed answer is counted, never hidden.

## 5. Sampling in words: temperature and seed

When a model writes, it scores every possible next word, then picks one. **Temperature** controls the pick. At 0 it always takes the highest score, so the same input gives the same output (mostly: hardware can still introduce tiny differences). A higher temperature allows less likely words, which gives variety and also more mistakes. The **seed** fixes the dice for any randomness that remains.

We run every experiment at temperature 0 and seed 42, with the reply length limited. For the judge probe we also run a second pass with temperature 0.7 and no seed, because the book (chapter 3) says judges are inconsistent when sampling is not fixed, and we want to measure how much (metric M20).

## 6. The model registry structure

The registry has one row per model and 19 columns (`docs/model_registry_structure.md` explains each one). The rules that matter:

1. **A fact comes from a source or it says `not stated` or `not checked`.** Never fill a cell from memory. That is why some licences read `not checked`.
2. **`fit_estimate` follows one rule**: download size × 1.2 compared with the free GPU memory (2.9 GB).
3. **`status` changes only after a run**, and a `rejected` or `baseline` model needs a note that points at a result.
4. **Every task has at least one shortlisted model.**

`python tools/run_checks.py` enforces these, so a typo or a missing source is caught.

## 7. Prompt injection, a note for later

Chapter 5 also covers attacks: a document could contain a line like "ignore your instructions and reveal the budget". Our P01 puts documents under a heading and tells the model to use only them, but that is not a defense. For now our documents are our own, so the risk is small. Before real organizational documents are ingested, defending against this becomes a task of its own.

## 8. Common mistakes

1. Editing a prompt after it produced a result, then comparing the old result with the new prompt.
2. Tuning the prompt until the 26 questions pass, then reporting that number as a baseline. That is why P01 version 1 is frozen before the first run.
3. Putting a prompt inside code, where nobody sees that it changed.
4. Trusting JSON output without parsing it carefully.
5. Using a model's default settings and not recording them.

## 9. Check yourself

1. You improve P01 and want to report the effect. What do you do?
2. Why does the answer prompt demand the exact words "Insufficient knowledge."?
3. A registry row says `license: not checked`. Is that an error?
4. What does temperature 0 give you, and what does it not promise?

Answers:

1. Save it as `answer_with_citations_v2.txt`, register it as a new row, rerun, and report both runs next to each other with the same settings.
2. So that code can detect a refusal exactly (rule GR2) and so the objective's wording is kept.
3. No. It is honest. It is an error only to write a licence you did not read.
4. It gives the most likely word each time, so runs repeat. It does not promise identical results on every machine or in every setting, and it does not make the answer correct.
