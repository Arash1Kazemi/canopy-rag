# M16 rubric: solution usefulness

Status: draft for supervisor review (Phase 9). No target: the target stays "to agree with supervisor".

## What M16 measures

From `metrics/metrics.csv`: the average human rating from 1 to 5 of the probable solution the system suggests for
each issue, I01 to I07 in `case_study/issues.csv`. Higher is better.

A probable solution is what the project proposal (section 12.5) asks the system to give after it has the issue, its
sub-issues, the knowledge and the executors: a source-based answer or solution path. The step that writes it is not
built yet, so this rubric is ready before the first run.

## Who rates, and what they see

- One person rates. Write your name or initials in the score sheet.
- For each issue, read the issue, the documents of its own node, and the suggested solution.
- Rate each issue on its own and in the order of the sheet. Do not change a rating after you see the average.

## Step 1: the checklist

Section 12.5 lists what a solution may hold. Answer each item `yes`, `no` or `not needed` in the score sheet. The
checklist helps you rate; it is not added up.

| Column | Question |
| --- | --- |
| `cites_sources` | Does each claim point to a document of the issue's own node? |
| `sources_correct` | Do the cited documents really say what the solution claims? |
| `gives_a_path` | Does it give a concrete next step or solution path, not only a restatement of the issue? |
| `names_limits` | Does it name known limits or conflicts, such as two documents that disagree? |
| `names_executor` | Does it name a suitable executor, when one is known? |
| `says_when_knowledge_is_missing` | When the node's knowledge is not enough, does it say so clearly? |
| `stays_in_node` | Does it use only the issue's own node (no knowledge of another node)? |

## Step 2: the rating from 1 to 5

| Rating | Meaning |
| --- | --- |
| 5 | Correct, grounded in the node's documents, and usable as it is: a clear path, its limits and missing knowledge named. |
| 4 | Correct and grounded, and usable after a small edit; one useful element is missing or vague. |
| 3 | Partly useful: the direction is right, but it is generic, misses an important limit, or cites weakly. |
| 2 | Hardly useful: mostly a restatement, or it relies on claims the documents do not support. |
| 1 | Not useful or harmful: wrong, invented, uses another node's knowledge, or hides that knowledge is missing. |

A solution that honestly says the knowledge is not enough, and names what is missing, is not a failure: rate how
useful that statement is (often 3 or 4). Any claim the documents do not support caps the rating at 2.

## Step 3: the number

M16 = the average of the seven ratings. Record it with the run date, the model tag and the prompt id as its source.

## Open points for the supervisor

- The anchors of the scale and the cap at 2 for an unsupported claim.
- Whether a second rater is needed (metrics.md: human-graded metrics depend on one person's rubric until a second
  person checks it).
