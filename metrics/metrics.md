# Metrics baseline

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Case study: the City (7 nodes in 4 layers).
Source: objective 20 of the proposal ("define clear indicators to evaluate each main component, reviewed with the supervisor"), and chapters 3 and 4 of "AI Engineering". Status: draft for supervisor review. Date: 2026-10-26.

## What this page decides

Step 5 of Phase 1 turns the eight objectives and the answer key into a table of metrics. This page says what each metric counts, how one answer is graded, which rules are checked as pass or fail, and how targets will be agreed. It sets no target, because a target needs a baseline first and a baseline needs the models of Phase 2. The data is in the CSV files of this folder, and `run_checks.py` keeps this page and the CSV files in step.

## Four words

| Word | Meaning | Example |
|---|---|---|
| Metric | A named rule that turns how well one component works into a number | Answer correctness: the share of answerable questions answered correctly |
| Baseline | The metric measured on the simplest working version, before any tuning | Measured in Phase 2 with plain chunks, one embedding model, one LLM |
| Target | The value a metric must reach to count as good enough | Agreed with the supervisor after the baseline exists |
| Hard rule | A rule that must hold on every run, checked as pass or fail | A node never uses another node's documents |

A metric is measured and can go up or down. A hard rule is either kept or broken, so it is tested, not measured.

## The metrics

`metrics.csv` has one row per metric, with its definition, unit, direction, data, grading rules, method, first phase, baseline and target. The table below is the index.

| ID | Metric | Objective | Component | Method | First measured in phase |
| --- | --- | --- | --- | --- | --- |
| M01 | Answer correctness | O1 | answering | automatic | 2 |
| M02 | Citation validity | O1 | answering | automatic | 2 |
| M03 | Correct refusal | O1 | answering | automatic | 2 |
| M04 | False refusal | O1 | answering | automatic | 2 |
| M05 | Answer faithfulness | O1 | answering | judge | 8 |
| M06 | Retrieval hit | O1 | retrieval | automatic | 2 |
| M07 | Context precision | O1 | retrieval | automatic | 2 |
| M08 | Context recall | O1 | retrieval | automatic | 2 |
| M09 | Version handling | O2 | answering | automatic | 2 |
| M10 | Duplicate detection recall | O2 | ingestion | automatic | 5 |
| M11 | False duplicate alarms | O2 | ingestion | automatic | 5 |
| M12 | Duplicate cited once | O2 | answering | automatic | 2 |
| M13 | Scanned text recovery | O2 | extraction | automatic | 2 |
| M14 | Terminal node accuracy | O3 | answering | automatic | 2 |
| M15 | Sub-issue suggestion recall | O4 | issues | human | 9 |
| M16 | Solution usefulness | O4 | issues | human | 9 |
| M17 | Research gap recall | O5 | issues | automatic | 12 |
| M18 | Judge and human agreement | O6 | judge | mixed | 11 |
| M19 | Judge score gap | O6 | judge | mixed | 11 |
| M20 | Judge repeatability | O6 | judge | automatic | 2 |
| M21 | Package detail fit | O6 | transfer | human | 10 |
| M22 | Time to first token | O7 | runtime | automatic | 2 |
| M23 | Generation speed | O7 | runtime | automatic | 2 |
| M24 | Question latency | O7 | runtime | automatic | 2 |
| M25 | Peak memory | O7 | runtime | automatic | 2 |
| M26 | Rule test coverage | O7 | engineering | automatic | 3 |
| M27 | RFP section completeness | O8 | rfp | mixed | 13 |
| M28 | Critique traceability | O8 | rfp | human | 13 |

Every objective has at least one metric. The baseline of Phase 2 fills M01 to M04, M06 to M09, M12 to M14, M20 and M22 to M25. The others wait for the phase that builds the component.

## Hard rules

`hard_rules.csv` lists the rules that are tested, not measured. Each one is assigned to a test area in the unit-testing rules.

| ID | Objective | Rule | Tested by |
| --- | --- | --- | --- |
| H01 | O3 | A node answers only from its own documents. Retrieval for a node never returns a chunk from another node. | unit test with a fake embedding model; evaluation on Q22 |
| H02 | O3 | The registry has exactly one root, and each layer is its parent's layer plus 1. | run_checks.py for the data; unit test for the code |
| H03 | O2 | Each knowledge item has exactly one active version. | unit test |
| H04 | O2 | An update adds a version and never deletes an old one. | unit test |
| H05 | O6 | A transfer package that scores below the judge threshold is never sent to the parent. | unit test with a stub judge |
| H06 | O7 | The system runs with the network off. No code calls an address outside localhost. | unit test that blocks the network; one manual run with the network off |
| H07 | O4 | Issue status and progress follow fixed rules: the same input always gives the same status and percentage. | unit test |
| H08 | O5 | The ranking of the 7 issues is the same on every run. | unit test with fixed inputs |
| H09 | O1 | Every answer has at least one citation, or it says insufficient knowledge. | unit test on the answer formatter; evaluation |
| H10 | O3 | A terminal node has one summary document and no child nodes. | run_checks.py |

## How one answer is graded

A grading rule decides whether one answer to one answer-key question is correct. The rule must give the same result on every run, so the grade never depends on a mood. The answer key has ten question types, and each type uses one to three rules.

| Question type | Grading rules |
| --- | --- |
| factual | GR1, GR5 |
| version_trap | GR1, GR5 |
| version_history | GR1, GR5 |
| terminal_node | GR1, GR5 |
| multi_document | GR1, GR5 |
| scanned_pdf | GR1, GR5 |
| duplicate | GR1, GR4, GR5 |
| contradiction | GR3, GR5 |
| unanswerable | GR2 |
| node_boundary | GR2 |

The rules are in `grading_rules.csv`. The required and forbidden facts of each question are in `key_facts.csv`. A fact is written in lowercase with no thousands separator, because the answer is normalized the same way before the comparison. Inside one question, `;` separates facts that must all appear, and `|` separates alternatives where one is enough.

Example, Q02 asks "How many electric buses does the agency run?" and the key fact is `25`. The answers "25", "About 25 buses are electric" and "25 of the 135 buses" all pass. The answer "32" fails.

### Where string matching fails

Matching key facts is the "contains the reference" variation of exact match from chapter 3 of the book. The book warns about its weak spot: "September 12, 1929" contains the year 1929 and is still wrong for a question about a birth year. For the same reason a right answer in unexpected words can fail. We keep the rule because it is cheap, exact and repeatable, and we cover its weak spots in three ways:

1. A question needs several facts together (Q12 needs seven), which makes a lucky match unlikely.
2. A refusal question lists forbidden facts, so an answer that leaks the Water Dept figure in Q22 fails.
3. A human reads every failed answer in the baseline run. Each failure is either a real model error or a grading rule bug, and a rule bug is fixed in `key_facts.csv` and noted. With 26 questions this is a few minutes of work.

Q06 is the weakest case. Its rule needs both routes and a conflict word, but a conflict word does not prove that the answer explains the conflict, so a human also reads every Q06 answer.

## How targets will be agreed

1. Phase 2 measures the baseline, and the value goes in `baseline` with its source in `baseline_source`.
2. You and your supervisor read the baseline next to each metric. For each metric you decide the lowest value that is still useful. Chapter 4 of the book calls this the usefulness threshold and shows a table with a hard requirement and an ideal value for each criterion.
3. The agreed value goes in `target`, and where and when it was agreed goes in `target_source`.
4. `run_checks.py` refuses a number in `target` without a `target_source`. So no target can appear without a decision behind it.

Until then every target reads `to agree with supervisor`.

## Design choices, and the book chapter behind each

| Choice | Why | Book |
|---|---|---|
| Measure each component on its own, then the whole system | If the answer is wrong, you must know whether retrieval or generation failed. Retrieval metrics (M06 to M08) are separate from answer metrics (M01 to M04). | Chapter 4, step 1 |
| Reference-based grading first, judge later | A reference answer gives an exact, repeatable result. A judge is flexible but inconsistent, so it must be checked against humans before it is trusted (M18 to M20). | Chapter 3 |
| Report results sliced by question type and by node | One average can hide a type that always fails. With 26 questions the slices are small, so read them as hints, not proof. | Chapter 4, step 3 |
| Retrieval precision and recall at document level | The answer key names the source files of each answer, so we can score retrieval without annotating every chunk. | Chapter 6 |
| Record the judge model and the judge prompt for every score | Judge scores are not comparable if the judge changes. A judge that you cannot see is not trusted. | Chapter 3 |
| Speed and memory next to quality | A good model that does not fit the laptop is not usable. Time to first token and the 90th percentile are the book's own examples. | Chapter 4 |

## Limits to keep in mind

- The case study is small. With 23 answerable questions, one question is worth about 4.3 percentage points, so a difference of one question is noise.
- M10 and M11 rest on one duplicate pair. Add more planted pairs before the ingestion baseline of Phase 5.
- Metrics that a human grades (M15, M16, M21, M28) depend on one person's rubric until a second person checks it.
- The book was written in 2024, so its examples of models are old. The metric ideas are not.

## To confirm with the supervisor

- The list of 28 metrics and the component split.
- The way targets are agreed: baseline first, then a usefulness value for each metric.
- Whether the key-fact grading is acceptable for the baseline, with a human reading every failure.
- Whether a judge score is allowed as a metric (M05) before the judge has been checked against human scores.
