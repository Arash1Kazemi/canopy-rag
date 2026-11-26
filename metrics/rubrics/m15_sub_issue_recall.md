# M15 rubric: sub-issue suggestion recall

Status: draft for supervisor review (Phase 9). No target: the target stays "to agree with supervisor".

## What M15 measures

From `metrics/metrics.csv`: of the known sub-issues of I01 (I02, I03 and I04), the share that the system suggests,
matched by a human. The unit is a share from 0 to 1, and higher is better.

The system suggests sub-issues with prompt P12. The run writes `results/issues/m15_I01_suggestions.csv`, one row per
suggestion, with an empty column `matches_known_sub_issue` (see the operator guide, part E).

## Who rates, and what they see

- One person rates. Write your name or initials in the score sheet.
- Read I01 and its three known sub-issues in `case_study/issues.csv` first.
- Rate each suggestion on its own. Do not change a rating after you see the total.

## Step 1: match each suggestion

For each row of the suggestions file, write in `matches_known_sub_issue` one of `I02`, `I03`, `I04` or `none`.

A suggestion matches a known sub-issue when both ask for the same action on the same thing. The words may differ.

| Known sub-issue | The action and the thing |
| --- | --- |
| I02 Verify ridership data | check or reconcile the ridership numbers (tap-in data against the survey) |
| I03 Pilot extra buses on Route 7 | try more buses (or shorter intervals) on Route 7 for a limited time |
| I04 Re-survey passengers | survey passengers again, including the groups the first survey missed |

Rules:

1. A suggestion matches at most one known sub-issue. If it fits two, pick the closer one and say why in `notes`.
2. A suggestion that only names the topic (for example "look at Route 7") and no action is `none`.
3. A suggestion that is much broader (for example "improve the bus network") is `none`.

## Step 2: fill the score sheet

In `m15_score_sheet.csv`, one row per known sub-issue:

- `found` is `yes` when at least one suggestion matches it, otherwise `no`.
- `matching_suggestions` lists the numbers of those suggestions, separated by `;`.
- Fill `run_file`, `model`, `rater` and `rated_on` (YYYY-MM-DD) in every row.

## Step 3: the number

M15 = (rows with `found` = `yes`) / 3. Record it with the run date and the model tag as its source.

## Open points for the supervisor

- Whether a partial match (the right thing, a different action) should count as half.
- Whether a second rater is needed (metrics.md: human-graded metrics depend on one person's rubric until a second
  person checks it).
