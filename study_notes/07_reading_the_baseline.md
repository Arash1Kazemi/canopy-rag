# Note 7: reading the baseline results

Where we are: after the runs. Book: chapter 3 (judges), chapter 4 (evaluate each component, slicing, usefulness), chapter 2 (sampling and thinking).
Files: `docs/baseline_report.md` and `docs/final_report.md`.

## In one minute

The numbers are only half the result. The other half is reading the answers behind them. Doing that, we found that one model's numbers were meaningless (it was a thinking-only model), and that four "wrong" answers were right and our grading was too strict. After that, the baseline is clear: a small model answers almost everything correctly when it gets the right documents, and it fails exactly where the case study planted problems.

## 1. Look at the answers, not only the score

`qwen3:4b` scored 0.91 in E2. That looks good. But its answers began "Okay, let me tackle this question…": it was writing its reasoning and was cut off at 256 tokens. The facts appeared in the reasoning, so the string rule counted them. Analogy: a student who hands in rough notes instead of an answer, and gets marks because the right number is somewhere on the page.

The cause: Ollama's metadata (`/api/show`) says this tag is the "Thinking" fine-tune, which cannot switch thinking off. Lesson: before you trust a model's number, read three of its answers, and check what the tag really is.

## 2. Grading bugs move metrics

| Question | Answer | Strict rule said | It really is |
|---|---|---|---|
| Q08 "Which route had the most complaints?" | "Route 7" | wrong, because it asked for "5 of 8" | right |
| Q19 | "11.4 million cubic metres" | wrong, because it asked for "22%" | right: the same loss, in volume |

Fixing four such rules moved M01 from 0.74 to 0.91. Both numbers are in the report, and the fix is written down. That openness is what keeps it honest. This is the book's point about evaluation guidelines (chapter 4): an unclear rule gives misleading scores.

## 3. Compare E2 and E3 to find the cause

E2 gives the model the right files, and E3 makes it retrieve them. For `phi4-mini`, 22 of 23 became 21 of 23. The one difference is Q03: retrieval returned the shift rules and their exact copy, so the model cited both. The cost of retrieval here is exactly the planted duplicate. Without the E2 run, we could not have said that.

## 4. When models tie

All three embedding models found every source at k=3. On 23 questions, `embeddinggemma` was one question better at k=1, which is noise. A tie on a small test does not mean the models are equal. It means the test cannot tell them apart. That calls for a larger test, not a coin flip.

## 5. Speed and quality together

`phi4-mini` answers in 0.7 s. `glm-ocr` reads a page perfectly but needs a minute. Both are fine for a system that indexes documents once and answers many questions: reading is done once per scan, and answering is done every time. Chapter 4 says to separate must-have from nice-to-have latency.

## 6. A good judge on an easy test

Both small models judged the 52 probe answers almost perfectly, and both caught the two reversed answers that the string rule accepted. But the reference was the expected answer itself, the easiest case. Chapter 3's warnings (inconsistency, self-bias, verbosity bias) are tested properly only on real packages in Phase 11.

## 7. Common mistakes

1. Trusting a number without reading the answers.
2. Fixing grading rules silently. Fix them, write them down, and report before and after.
3. Choosing between tied models by the last decimal.
4. Reporting a model's speed when it was thinking.

## 8. Check yourself

1. Why is `qwen3:4b` excluded from the baseline?
2. M01 went from 0.74 to 0.91 after the grading fixes. Did the model improve?
3. What does the gap between E2 and E3 tell you here?

Answers:

1. It is a thinking-only version, so its answers are reasoning cut off at the limit, not answers. Its numbers do not measure what the metric means.
2. No. The model's answers did not change. Only the grading got fairer, which is why both numbers are reported.
3. Retrieval cost one question, and that question is the planted duplicate: the index holds two copies, so the model sees and cites both.
