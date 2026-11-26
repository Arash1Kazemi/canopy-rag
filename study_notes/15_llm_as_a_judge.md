# Note 15: LLM as a judge (Phase 10)

Where we are: Phase 10. Book: chapters 3 and 4 (evaluation, and AI as a judge).
Files: `rag_core/judging/` (rubric, parser, threshold, model, prompt, judge, repository), `rag_core/workflows/judge_prompts.py`, `prompts/judge_rubric_v1.txt` (P14), `rag_core/cli_judge.py`, `rag_core/infrastructure/sqlite_judging.py`.
Decisions: A68 to A75 in `architecture/architecture.md`. Prepared run: `docs/operator_guide.md`, part G (not run).

## In one minute

Until now a person had to read every output and say "good enough". The **judge** is a second model call that reads an output and gives it a score out of 20. The system then compares the score with a **threshold** (18) and decides pass or fail. The hard part is not asking the model. The hard part is not believing it too easily.

## 1. The idea: a teacher with a marking sheet

**Analogy.** A teacher marks an essay with a sheet: 5 points for facts, 4 for completeness, and so on. The marks must add up to 20. The head of school then says: below 18 does not go to the parent class. The teacher does not decide who goes. The teacher only fills in the sheet.

**Precise idea.** There are four parts, and each is small:

| Part | Job | Where |
| --- | --- | --- |
| Rubric | The marking sheet: 7 criteria with points, total 20 (A68) | `judging/rubric.py` |
| Judge prompt | Tells the model what to read, and to answer with one JSON object (A73) | `prompts/judge_rubric_v1.txt` |
| Strict parser | Reads the reply. Anything odd is a failed judgment (A70) | `judging/parser.py` |
| Threshold | The pass mark, one per layer, read from the layer registry (A69) | `judging/threshold.py` |

The flow in words: render the prompt, ask the model, parse the reply, compare the total with the threshold of the layer that receives the output, store everything.

**The key rule.** The model never decides pass or fail. It only writes numbers. The code adds them up again, checks them, and decides (A71). If the model says "passed: true", the parser refuses the whole reply.

## 2. One example from the City

N4 (the Transit Agency, layer 2) wants to send "The Transit Agency has 135 buses [D10_bus_fleet_inventory_v2]." up to N1 (layer 1). The target layer is 1, and its threshold is 18.

| Reply of the model | What the system does |
| --- | --- |
| Valid JSON, total 19 | pass (19 is at least 18) |
| Valid JSON, total 17 | fail (17 is below 18) |
| `Score: 20/20, great!` | failed judgment, stored, not a pass |
| JSON with `"total": 25` | failed judgment (the maximum is 20, and 25 does not match the criteria) |
| JSON wrapped in a code fence | failed judgment (no repair, A70) |

The failed judgment is stored with the raw reply and the reason. That is on purpose: if the model fails often, you want to see why.

## 3. Repeatability: does the judge give the same answer twice?

A judge that says 19 today and 16 tomorrow for the same text is useless as a gate. So we run it twice on the same prompt and compare (metric M20).

- The two **decisions** agree if both are valid and both say pass, or both say not pass.
- The two **totals** may still differ (19 and 20). We record that separately.
- A failed judgment never counts as agreement (A72). Two garbage replies do not make a stable judge.

With temperature 0 and a fixed seed, two runs are very likely identical. That is repeatability of the setup, not proof that the judge is right. A judge can be wrong in the same way every time.

## 4. Where the book matters

Chapter 3 and 4 warn about three things, and each shows up here:

- **Self-preference.** A model tends to like its own kind of output. Our judge and our answer model are both phi4-mini by default (A75). Be careful with high scores.
- **Judges are not ground truth.** The score only means something after you compare it with a human. That is M18 (same accept or reject as a human) and M19 (the average gap in points). Those need about 20 packages, from Phase 11.
- **Prompts and rubrics are versioned.** A score without its prompt version and rubric version cannot be compared later. Every stored score has both.

## 5. Common mistakes

- Trusting the number the model gives for "total". Add the criteria again (we do).
- Letting the model say pass or fail. The threshold belongs to the layer registry, so the supervisor can change it in one place.
- "Repairing" a reply that is almost JSON. It feels helpful, but every repair is a guess, and a guess is how a bad package gets through. If the model needs a repair rule, make it a separate, written decision.
- Writing 18 in the code. The number is data (`registry/layer_registry.csv`). The only 18 in the code is the proposal default for a layer whose rule has no score.
- Counting repeatability on garbage replies.

## 6. Check yourself

1. A model replies with total 20, but the seven criteria add up to 18. What does the system store, and why not "18, pass"?
2. The supervisor says layer 1 needs only 16. Which file do you change, and what happens to layer 0?
3. Two runs give 19 and 20. Is the judge repeatable by M20? What would change if they gave 17 and 18?

(Answers: 1. A failed judgment: the model contradicted itself, so we do not know which number is true, and guessing is how a bad package passes. 2. `registry/layer_registry.csv`, the `min_judge_score` of layer 1; layer 0 keeps 18. 3. Yes, same decision (both pass), though the totals differ. With 17 and 18 the decisions differ (fail and pass), so no.)

## 7. What is not done

The judge is built and tested with a stub, not run on a real model (part G of the operator guide). The actions the proposal lists after a low score (generate again, or suggest a fix) come with the transfer package in Phase 11. The M18 and M19 sheets for a human also come in Phase 11.
