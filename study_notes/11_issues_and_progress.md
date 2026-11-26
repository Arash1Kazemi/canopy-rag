# Note 11: issues, statuses, progress and sub-issue suggestions (Phase 7)

Where we are: Phase 7. Book: chapter 5 (prompt engineering), for the prompt that suggests sub-issues.
Files: `rag_core/issues/` (the domain), `rag_core/workflows/issues.py` (the use cases), `rag_core/infrastructure/sqlite_issues.py`, `config/issue_progress_weights.csv`, `prompts/suggest_sub_issues_v1.txt` (P12), and the commands in `rag_core/cli_issues.py`.

## In one minute

An **issue** is a problem, question or need that lives in one node. Phase 7 gives issues a life: ten statuses with fixed moves between them, a progress number computed by fixed rules (H07), sub-issues in a set order, a way to spot an issue that looks like one we already have, and a language model that suggests sub-issues for a person to accept or reject.

## 1. Statuses: a board game with fixed moves

**Analogy.** A board game. Your piece moves only along the arrows. You cannot jump from "start" to "finish".

**Precise idea.** The proposal (14.1) lists ten statuses: new, analyzing, knowledge identified, executor identified, solution proposed, in progress, awaiting decision, solved, unsolved, archived. It does not say which moves are allowed, so we wrote a table (decision A30). Work goes forward. A person may step back to "analyzing" when new facts appear. "Archived" is the end.

**Example.** I04 "Re-survey passengers" is `new`. `new -> analyzing` is allowed. `new -> solved` is refused with a message that lists the allowed moves.

The old file used five values. They keep their meaning: "in progress" becomes `in_progress`, the others keep their names.

**Common mistake.** Letting any code set the status field directly. Then the table means nothing. Here the status changes only through `with_status`, which checks the table.

## 2. Progress: a weighted checklist

**Analogy.** A school report where homework counts 20 percent and the exam counts 80 percent. Each part has a weight, and the weights add up to 100.

**Precise idea in words.** The proposal names seven things that show progress (14.1). Each is a **factor**:

| Factor | Done when | Weight (untuned) |
| --- | --- | --- |
| sub-issues defined | it has at least one sub-issue | 15 |
| supporting knowledge | a knowledge item is linked | 15 |
| executor mapped | an executor is linked | 10 |
| solution proposed | a solution text is written | 20 |
| research completed | marked complete | 10 |
| sub-issues solved | the **share** of its sub-issues that are solved | 20 |
| review approved | marked approved | 10 |

For each factor, take how much of it is done (all, nothing, or a share), times its weight. Add the results. Round down. Only a solved issue shows 100; any other issue stops at 99 (decision A31). The weights live in a config file and are **not tuned**: they are starting values for the supervisor.

**Example.** I01 has three sub-issues and one of them (I03) is solved. Sub-issues defined gives 15. Sub-issues solved gives one third of 20, which is 6.67. Nothing else is done yet. 15 + 6.67 = 21.67, rounded down: **21%**.

**H07 in a test.** The same issue and sub-issues must always give the same number. The test feeds the five sub-issues in every possible order (120 orders) and checks there is only one answer. This works because the rule only counts; it never looks at order.

**Common mistake.** Treating 21% as a measured fact. It is the result of weights nobody has tuned. Change the weights and the number changes.

## 3. Comparing a draft: counting shared words

**Analogy.** Two shopping lists. The more items they share, the more alike they are.

**Precise idea in words.** Take the words of the draft and of each existing issue. Remove **stopwords** (little words like "the", "on", "is" that every text has). Count the words both have. Divide by the number of different words in the two together. 1 means the same words, 0 means nothing in common. This is the Jaccard score.

Two rules matter more than the score:

- Only issues of the **same node** are compared (proposal 12). An N4 issue is never a candidate, even if it uses the same words.
- There is **no threshold** that says "duplicate". You get a ranked list to read (decision A34). A threshold needs labelled pairs first, the same lesson as M10 and M11 for documents.

**Example from the city.** Draft in N6: "Crowding on Route 7 at peak. Peak load on Route 7 is too high for passengers." I01 says "Route 7 overcrowded at peak. Peak load above the 85% policy limit on Route 7". They share *route*, *7*, *peak* and *load*, so I01 comes first.

Notice "crowding" and "overcrowded" do not match: they are different words. That is the weakness of word counting. Phase 8 can plug embedding similarity into the `similarity` slot, which compares meaning instead of spelling. The shared words are still shown, so a person sees a reason.

**Common mistake.** Removing numbers with the stopwords. "Route 7" and "Route 12" must stay different, so numbers are kept.

## 4. Sub-issue suggestions: the model proposes, a person decides (book chapter 5)

**Analogy.** An assistant writes a to-do list on sticky notes. You keep some, rewrite one, and throw the rest away. Only the notes you keep go on the board.

**Precise idea.** The prompt P12 (`prompts/suggest_sub_issues_v1.txt`) follows chapter 5: give the context (field of activity, title, description), a clear task (3 to 5 sub-issues), a constraint (use only the given facts, invent no numbers) and an exact output format (`- title | description`, one per line). A fixed format makes the reply easy to parse in plain Python. The prompt is versioned and registered, so a later v2 can be compared with v1.

Then the person accepts, edits or rejects each suggestion. The accepted ones are saved **together in one transaction**: if one fails, none is kept (decision A35). A model reply never creates an issue by itself.

**Example.** The commands:

```
python -m rag_core suggest-sub-issues --issue I01 --out results/issues/m15_I01_suggestions.csv
python -m rag_core accept-sub-issues --issue I01 --from results/issues/m15_I01_suggestions.csv --take 1,3
```

To edit a suggestion, change its title in the CSV before you accept it. Rows you do not list are rejected.

**Measuring M15 (prepared, not run).** M15 asks: of I01's known sub-issues (I02, I03, I04), how many does the model suggest? Run the first command above with Ollama on 127.0.0.1:11500, then fill the column `matches_known_sub_issue` with I02, I03, I04 or none. The prompt never shows the known sub-issues, so the model cannot copy the answer. With no model running, the command fails politely and changes nothing.

**Common mistake.** Putting the existing sub-issues into the prompt "for context". Then M15 measures copying, not suggesting.

## 5. Where an issue stands (12.3)

Sub-issues of one parent have a **position**: 1, 2, 3. They are listed in that order, so the order is the same on every run. `show-issue` also shows the parent, the sub-issues, what the issue is **blocked by**, what it **blocks**, and other issues in the same **category**. Blocked-by links stay inside one node and may never form a loop (I02 waits on I04, I04 waits on I02 is refused): a loop has no order in which to do the work.

## Questions

1. I03 is solved and every factor of I01 is done except "sub-issues solved". Why is I01 not at 100?
2. A draft in N6 has the same words as I05, which is in N4. Where does I05 appear in the ranked list?
3. Why does the suggestion prompt not list I02, I03 and I04?

## Answers

1. Two reasons. Sub-issues solved is only one third done (one of three). And only a solved issue shows 100; I01 is still `analyzing`, so it stops at 99 at most.
2. Nowhere. Comparison looks only at the draft's own node, so an N4 issue is never a candidate.
3. Because M15 checks whether the model finds them. If the prompt showed them, the model could copy them and the metric would be meaningless.
