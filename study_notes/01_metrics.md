# Note 1: the metrics baseline

Where we are: step 5. Book: chapter 3 (evaluation methodology), chapter 4 (evaluate AI systems), chapter 6 (retrieval metrics).
Files made in this step: `metrics/metrics.md`, `metrics/metrics.csv`, `metrics/grading_rules.csv`, `metrics/question_type_rules.csv`, `metrics/key_facts.csv`, `metrics/hard_rules.csv`.

## In one minute

A metric is a rule that turns "does it work?" into a number. Before we measure anything we must decide, for each of the 26 questions, what counts as a correct answer, so that the same answer always gets the same grade. We wrote 28 metrics, 5 grading rules and 10 hard rules. We set no target, because a target is the pass mark, and you cannot set a pass mark before you know what the simplest version scores.

## 1. Metric, baseline, target

Analogy: a fitness test. The metric is "how many push-ups in one minute". The baseline is what you manage on day one, before any training. The target is the number your coach and you agree on after seeing the baseline. Nobody sets "100 push-ups" on day one without knowing whether you can do 5 or 50.

| Word | In this project | Who decides |
|---|---|---|
| Metric | Answer correctness: share of answerable questions answered correctly | You, in this step |
| Baseline | The value measured in Phase 2 with the simplest setup | The experiment |
| Target | The lowest value that is still useful | You and your supervisor, after the baseline |

The common mistake is to write the target first. Then the target is a guess, and the project either fails a number it never had a chance to meet or celebrates a number that was too easy.

## 2. How do you decide an answer is right?

The book (chapter 3) names the ways. When you have a reference answer, the metric is called reference-based.

| Way | How it works | Good for | Weak spot |
|---|---|---|---|
| A human reads it | A person judges | Anything | Slow, and people disagree |
| Exact match | The answer equals the reference | Short answers: a number, a name | A right answer in other words fails |
| Lexical similarity | Count how many words, or word groups, overlap (BLEU and ROUGE do this) | Translation, summaries | Looks alike is not means alike |
| Semantic similarity | Turn both texts into lists of numbers (embeddings) and compare | Longer answers | Only as good as the embedding model |
| AI as a judge | A model reads the answer and scores it | Open-ended answers | Inconsistent and biased |

Semantic similarity, in words. An embedding model turns a text into a list of numbers, like a point on a map of meaning. Cosine similarity compares two such lists as two arrows: if they point the same way the score is 1, if they are at right angles it is 0, and if they point opposite ways it is minus 1. "What's up?" and "How are you?" share no words, but their arrows point almost the same way.

## 3. Your Q02 exercise, answered

The question: "How many electric buses does the agency run?" The expected answer is `25`. The model says "about 25 of our buses are electric". Is it correct?

Yes. The facts are right, and the extra words do not matter. The rule we wrote: **normalize the answer (lowercase, drop thousands commas), then check that every required fact is inside it and no forbidden fact is.** The book calls this the "contains the reference" variation of exact match.

```python
def is_correct(answer, required_groups, forbidden):
    text = normalize(answer)
    has_all = all(any(alternative in text for alternative in group) for group in required_groups)
    return has_all and not any(fact in text for fact in forbidden)
```

| Answer | Verdict | Why |
|---|---|---|
| `25` | correct | the fact is there |
| `About 25 buses are electric.` | correct | extra words are fine |
| `25 of the 135 buses.` | correct | contains 25 |
| `32` | wrong | the fact is missing |
| `Twenty-five` | wrong | a right answer in other words: a false negative |

Why not exact match? The answer `About 25 buses` would fail. Why not an AI judge? It costs time, it can disagree with itself, and for a plain number it adds nothing.

The weak spot is real. The book's own example: for "What year was Anne Frank born?" the output "September 12, 1929" contains 1929 but is wrong. In our case, "load rose from 71% to 94%" contains both numbers of Q11 but reverses the meaning. That is why `experiments/judge_probe.csv` has two such answers on purpose, why a question needs several facts together, and why a human reads every failed answer in the baseline run.

Facts are written in `metrics/key_facts.csv`. A `;` means "and", a `|` means "or". Q12 (the scanned minutes) needs seven facts at once, so a lucky match is very unlikely.

## 4. Retrieval metrics: precision and recall

Analogy: fishing. The lake holds the fish you want (the answer-key sources). You cast a net and pull up some things. Precision: of everything in the net, how much is the fish you wanted? Recall: of all the wanted fish in the lake, how many did you catch?

Example, Q06 needs two files (D11 and D16). The system retrieves 3 chunks: one from D11, one from D07, one more from D11.

- Precision: 2 of the 3 chunks come from a wanted file, so 2/3.
- Recall: 1 of the 2 wanted files was found, so 1/2.
- Hit: at least one wanted file was found, so yes.

Why both? A system can reach recall 1 by returning everything (and have terrible precision), or precision 1 by returning one safe chunk (and miss the second file). The book (chapter 6) gives both as the standard pair for a retriever.

## 5. Why a judge is not trusted yet

The book (chapter 3) is clear: AI judges are fast, cheap and flexible, and one study reported 85% agreement with humans, higher than the 81% among humans. But:

- **Inconsistency.** The same judge on the same input can give different scores on two runs. We measure this (M20).
- **Biases.** A judge favours its own answers (self-bias), the first of two answers (position bias), and longer answers (verbosity bias).
- **Unclear criteria.** Three tools used the word "faithfulness" with three different prompts and scales (1 to 5, 0 or 1, yes or no). The book's rule: do not trust a judge if you cannot see its model and prompt. So we version the judge prompt and record the judge model.

Our plan: check the judge against human scores (M18 to M20) before its scores can accept or reject anything.

## 6. Test each component on its own

The book (chapter 4, step 1) gives this example: an app extracts a person's employer from a PDF. If the answer is wrong, was it the PDF reading or the extraction? Only if you test them apart do you know.

Ours: for the scanned minutes D19, M13 tests only whether the vision model read the text. Q12 and Q13 test the whole path. If Q12 fails and M13 is high, the problem is later. Likewise retrieval (M06 to M08) is separate from answering (M01 to M04), and Phase 2 runs the answering test once with the right files (so retrieval cannot fail) and once with real retrieval.

## 7. Speed metrics, in words

- **Time to first token**: how long you wait before the first word appears.
- **Tokens per second**: how fast the words come after that. A token is a piece of a word.
- **90th percentile**: sort all the times, and take the value that nine out of ten are at or below. It tells you the slow-but-common case, which an average hides. The book uses it in its example table.

## 8. Metrics versus hard rules

"A node answers only from its own documents" is not a number that goes up and down. It either holds or it is a bug. So it is a hard rule, tested with a pass or fail unit test (H01), not measured. Mixing the two is a common mistake: you do not set a target of "99% node isolation".

## 9. Common mistakes

1. A target before a baseline.
2. One average for everything. Slice by question type and node, and read the slices as hints, because 26 questions is small. The book also warns about Simpson's paradox: a model can win in every subgroup and still lose overall.
3. Tuning prompts on the same 26 questions you report. The result then flatters you.
4. Trusting a judge without checking it against humans.
5. Treating a metric as true because it is a number. The rule behind it can be wrong, and a person should read the failures.

## 10. Check yourself

1. Q05 expects `15.2 million`. A model answers "15,2 million trips". Does the rule pass it? What would you change?
2. A retriever returns 4 chunks, all from the right file, but the question needs 2 files and only one is found. What are the precision and the recall?
3. Why is "never use another node's documents" a hard rule and not a metric?
4. Why do we run the answering test once with the right files given?

Answers:

1. No: `15.2` is not inside `15,2`. The facts file could accept `15,2` as an alternative (`15.2|15,2`), which is a rule fix, and it would be recorded. The lesson is that a human reading failures finds such rule bugs.
2. Precision is 4/4 = 1, recall is 1/2 = 0.5.
3. It must hold on every run, so it is checked as pass or fail. A percentage would allow some leaks.
4. So that a wrong answer can only be the language model's fault. The difference between that run and the real run is the cost of retrieval mistakes.
