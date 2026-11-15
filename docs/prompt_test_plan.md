# Prompt test plan

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Source: steps 3 and 4 of Phase 2, chapters 2, 4, 5 and 6 of "AI Engineering", and the metrics in `metrics/metrics.md`. Status: draft, written before the first run. Date: 2026-10-26.

## What this plan decides

How we try the shortlisted models so that the results can be trusted and repeated: what stays fixed, what each experiment asks, what it records, and how a result is read. The experiments are in `experiments/experiments.csv`, the code is in `baseline_runner/`, and the prompts are in `prompts/prompt_registry.csv`.

## The experiments

| ID | Experiment | Metrics |
| --- | --- | --- |
| E1 | Retrieval | M06, M07, M08 |
| E2 | Answers from the right files | M01, M02, M04, M09, M12, M14, M22, M23 |
| E3 | Whole path | M01, M02, M03, M04, M09, M12, M14, M22, M23, M24, M25 |
| E4 | Reading a scanned page | M13 |
| E5 | Judge probe | M20 |
| E6 | Speed and memory with more context | M22, M23, M24, M25 |

Every metric that the metrics page marks as first measured in Phase 2 is covered by at least one experiment.

## What stays the same

Chapter 5 of the book says to test prompts systematically: version them, and use the same metrics and the same data every time, so two results can be compared. These settings are fixed in `baseline_runner/config.py` and are written into `meta.json` of every run.

| Setting | Value | Why |
|---|---|---|
| Temperature | 0 | The model picks its most likely word each time, so a run repeats (chapter 2 explains sampling) |
| Seed | 42 | A fixed starting point for anything that is still random |
| Context size | 4096 tokens | Ollama's default for a GPU of this size, and enough for 12 short chunks. It is set explicitly, so a default change cannot change a result |
| Reply length limit | 256 tokens (1024 for reading a page) | Answers are short. A limit stops a model that rambles from skewing the speed numbers |
| Thinking mode | off, for models that list it | A thinking model writes a long hidden text first, which would make its speed and answers not comparable |
| Prompt | one user message, from the registry | No hidden system prompt. The prompt id and version are known |
| Chunk setting | `words80` (80 words, 15 overlap), with `file` as a comparison | The simplest usual setting, so it is the baseline |
| Chunks per question | 3 | A usual small value, and it is varied in E1 and E6 |

## E1: Retrieval

- **Question.** Which embedding model puts the answer-key sources first?
- **Set up.** Each embedding model embeds every chunk with its own document prompt, then every question with its own query prompt. The prompts follow the model cards, because the right prefix changes the result. Retrieval stays inside the node that asks (hard rule H01).
- **Records.** The hit, the precision and the recall of every question at k of 1, 3 and 5, for both chunk settings, and the time to embed.
- **Reading it.** Pick the model with the best recall at k of 3. If two models are within one question of each other, prefer the multilingual one, because Persian comes later. The hit rate can only stay the same or rise as k grows, and a drop would mean a bug.
- **Risks.** With 23 questions one question is worth about 4.3 percentage points. Several short documents mean that `file` and `words80` can look the same.

## E2: Answers from the right files

- **Question.** How well does each LLM answer when retrieval cannot fail?
- **Set up.** For each answerable question the prompt P01 gets the full text of its answer-key source files. A mistake here is the LLM's mistake. This follows chapter 4: evaluate each component on its own, or you do not know which one failed.
- **Records.** The answer, the citations, the grading rules, and the speed of each call.
- **Reading it.** A model that fails here cannot be saved by better retrieval. Look at which question types fail.
- **Risks.** The oracle files are short, so a long context is not tested here (that is E6).

## E3: Whole path

- **Question.** How much do retrieval mistakes cost, and does the LLM refuse when it should?
- **Set up.** The best embedding model of E1 retrieves 3 chunks inside the asking node, and each LLM answers from them. All 26 questions are asked, including the three that must be refused.
- **Records.** Everything E2 records, plus the retrieved files and whether they were right.
- **Reading it.** The gap between E2 and E3 for one LLM is the cost of retrieval. Q01 and Q26 test versions, Q03 tests the duplicate, Q22 tests the node boundary, and Q23 and Q24 test refusing.
- **Risks.** The baseline indexes all 22 files, so the old fleet inventory and the duplicate are in the index on purpose. We expect failures there, and Phases 4 and 5 are meant to fix them.

## E4: Reading a scanned page

- **Question.** Can an LVM read the minutes D19 from an image?
- **Set up.** `scripts/render_d19.ps1` draws D19 as a clean image and as a turned, blurred image. Each LVM reads both with its own prompt (P03 for the OCR model, P02 for the others).
- **Records.** How many of the seven facts of Q12 and Q13 appear in the text, which are missing, and the text itself.
- **Reading it.** The clean image shows whether the model can read at all. The degraded image shows how fast it breaks. A fact that is missing is read by a human to see whether it was misread or skipped.
- **Risks.** A drawn page is easier than a real scan. A real scan is a later test (Phase 4).

## E5: Judge probe

- **Question.** Can a small LLM tell a right answer from a wrong one, and give the same verdict twice?
- **Set up.** `experiments/judge_probe.csv` has 52 labelled answers, one right and one wrong for each question. The judge prompt P04 gives the question, the reference answer and the answer to check, and asks for JSON. Each item is judged twice at the fixed settings, and twice with default sampling (temperature 0.7, no seed).
- **Records.** Accuracy against the label, the share of items with the same verdict twice (M20), and accuracy on the two wrong answers that string matching accepts.
- **Reading it.** Chapter 3 warns that judges are inconsistent and biased. A judge that is wrong on many items, or flips between runs, is not ready to accept or reject transfer packages. This probe is a first look, not the real check, which is M18 to M20 in Phase 11 on packages.
- **Risks.** The reference is the expected answer itself, which is the easiest case. The judge model is also one of the models being answered, which invites self-bias (chapter 3).

## E6: Speed and memory with more context

- **Question.** How do speed and memory change as more chunks go into the prompt?
- **Set up.** Q06, Q12 and Q25 are asked with 1, 3, 6 and 12 chunks. After each model and k, the GPU split is read with `ollama ps`, and the memory in use is read with `nvidia-smi` and the process list.
- **Records.** The time to first token, the speed in tokens per second, the question latency, and the memory.
- **Reading it.** Look for the k where the prompt no longer fits the GPU and the speed drops. That is the practical limit of this laptop.
- **Risks.** Memory is read after each question, not continuously, so the true peak can be a little higher.

## Grading and human review

Answers are graded by the rules in `metrics/grading_rules.csv`. The first run is also read by a human: every answer that fails is read once, and Q06 is always read. A failure is either a model error, or a grading rule bug. A rule bug is fixed in `key_facts.csv`, noted in the report, and the run is graded again. The known blind spots of the rule (a reversed number, a swapped pair) are in the judge probe.

## Keep the answer key honest

We choose models and prompts by looking at the same 26 questions that we then report. That flatters the result, because a prompt can be tuned until these 26 pass. Rules to limit this:

1. Prompt P01 version 1 is frozen before the first run. A change is a new version, a new run, and both results are reported.
2. The baseline is the first run, not the best run.
3. Before the Phase 3 design is final, write new questions that no prompt was tuned on, and check the chosen setup on them. The answer key stays as it is.

## Order of work and stop rules

1. Check that the server answers and the shortlisted models are ready (`check`).
2. Render the D19 images.
3. Run E1, then choose the embedding model.
4. Run E2, E3, E4, E5 and E6.
5. Stop and write down a model that will not load, or that is far too slow, instead of forcing it.

## What is recorded for every run

The results folder holds the CSV files, and `meta.json` holds the date, the Ollama version, the digest of every downloaded model, and the settings. A result is only comparable with another one that has the same digests and settings.

## To confirm with the supervisor

- That the first run is the baseline, and that later improvements are measured against it.
- The plan to write new, unseen questions before the design is final.
- That a probe of 52 answers is enough for a first look at the judge.
