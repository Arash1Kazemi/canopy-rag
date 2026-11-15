# Note 6: run the models, try the prompts, find the limits

Where we are: steps 2 (a way to run the models locally), 3 (sample prompt experiments) and 4 (find the limits of offline performance). Book: chapter 2 (sampling, hallucination), chapter 3 (judges), chapter 4 (latency, model selection).
Files made: `docs/how_to_use_the_models.md`, `docs/prompt_test_plan.md`, `experiments/experiments.csv`, the code in `baseline_runner/`, and the tests in `tests/`.

Honest status: the code and its 63 tests are written and pass with test doubles. **No real model has been run yet**, because the downloads need your approval. Nothing below claims a result.

## In one minute

A model server is a small program that stays open on your computer. Your code sends it a request on the address `127.0.0.1` (which means "this computer") and reads the reply. Nothing leaves the laptop. We wrote a runner that asks the 26 questions through retrieval and a model, grades each answer with the rules from Phase 1, and writes the results to CSV files. Six experiments probe different things, so that a failure can be traced to its cause.

## 1. How a local model runs

Analogy: a restaurant kitchen with a serving window. The kitchen (the model server) stays open. You hand an order through the window (an HTTP request containing JSON) and you get a dish back (a JSON reply). The window is inside the building, so nobody outside can order and nothing is sent out.

```python
reply = client.chat("qwen3:4b", [{"role": "user", "content": prompt}], think=False)
print(reply.text)               # the answer
print(reply.stats.tokens_per_s) # how fast it wrote
```

The reply also carries its own timings, in nanoseconds: how long loading took, how long reading the prompt took, how many tokens were written and how long that took. Our client turns them into seconds. Time to first token is estimated as loading plus prompt reading, because we do not stream the reply.

## 2. The pipeline in the runner

```
files -> chunks -> embedding model -> vectors -> search inside the node -> top k chunks
                                                                    |
question -> prompt P01 (chunks + question) -> LLM -> answer -> grade (GR1..GR5) -> metrics -> CSV
```

| Module | Does |
|---|---|
| `corpus.py` | Reads the 22 files and 26 questions (read-only) |
| `chunking.py` | Cuts a file into windows of 80 words with 15 overlapping |
| `retrieval.py` | Compares vectors with cosine similarity, and only inside one node |
| `prompts.py` | Fills a prompt template and refuses a wrong set of blanks |
| `ollama_api.py` | The one place that talks to the server |
| `fakes.py` | Test doubles: a fake embedder and a fake client |
| `grading.py` | The five grading rules |
| `metrics.py` | Precision, recall, medians, the 90th percentile, the summary |
| `experiments.py` | The six experiments |

Chunk and overlap in words: a chunk is a window of words, and the overlap repeats the last few words in the next chunk so that a sentence cut at the edge still appears whole in one of them. The book (chapter 6) says there is no best size: you experiment, which is why E1 tries two settings.

## 3. The six experiments, and what each one tells you

| | Question | If it goes badly, the cause is probably... |
|---|---|---|
| E1 | Which embedding model finds the right files? | The embedding model, its prefix, or the chunking |
| E2 | How well does each LLM answer from the right files? | The LLM or the prompt |
| E3 | The same, with real retrieval, and refusals | Retrieval (compare with E2), or the LLM's refusal behavior |
| E4 | Can the LVM read the scanned minutes? | The LVM, the image quality, or the prompt |
| E5 | Can a small LLM judge right from wrong, repeatably? | A small judge is not reliable enough yet |
| E6 | What do speed and memory do as context grows? | The model no longer fits the GPU |

Reading E2 against E3 is the central trick, from chapter 4 step 1: E2 removes retrieval as a cause, so the gap between them is the cost of retrieval mistakes.

## 4. Finding the limits

"Limits of offline performance" has four sides, and each has a measurement:

1. **Quality limit.** Where does a small model fail? E2 and E3 by question type: numbers, versions, conflicts, refusals.
2. **Memory limit.** How much of the model fits the GPU? `ollama ps` shows the GPU and CPU split, and E6 shows what happens as k grows.
3. **Speed limit.** Time to first token, tokens per second, and the 90th percentile of the question latency. A model that is right but takes a minute per question may not be usable.
4. **Reading limit.** E4's clean page against the turned, blurred page shows how quickly reading breaks.

## 5. What these results will not prove

- **The sample is small.** 23 answerable questions: one question is about 4 percentage points. Do not read a gap of one question as a difference.
- **Prompts and models are chosen on the same questions that are reported.** That flatters the baseline. We freeze the first prompt and later test on new questions.
- **One run.** At temperature 0 runs repeat well, but not perfectly across hardware setups.
- **A drawn page is easier than a real scan.** E4 is a first look.
- **The judge probe uses the easiest case**: the reference is the expected answer itself.

## 6. What happens after the first run

1. Read every failed answer. Decide: model error, or rule bug. Fix rule bugs in the key facts and note them.
2. Write the baseline report with the tables, the failures by type, and the limits.
3. Put the baseline values in `metrics/metrics.csv`, each with its source run. The checker then requires the source.
4. Update the registry: statuses and evaluation notes with pointers to result folders.
5. Take the baseline to your supervisor, and agree the targets.

## 7. Common mistakes

1. Running the real experiments before the pipeline is tested with test doubles. Ours found a crash on Q12 before any download.
2. Changing the settings between models.
3. Reading a single answer instead of the pattern.
4. Ignoring `ollama ps`. A slow model is often a model that did not fit.
5. Saying "offline" without proving it. Switch the network off and run it.

## 8. Check yourself

1. E2 gives 80% and E3 gives 50% for the same LLM. Where is the problem?
2. Why does the runner retrieve for all questions first, and then run each LLM?
3. What does the 90th percentile tell you that the average does not?
4. Is a model that gets every question right in E2 "good enough"?

Answers:

1. Mostly in retrieval or in refusals: the LLM does well when it gets the right files, and loses 30 points when it must work with what retrieval finds.
2. The GPU is small. Switching between the embedding model and the LLM for every question would reload models again and again. Doing all retrieval first swaps once.
3. How slow the slow-but-common questions are. A few fast answers can hide that one in ten takes much longer.
4. Not yet. E2 gives it the right files. It must also pass E3 (real retrieval and refusals), fit the laptop, and be fast enough.
