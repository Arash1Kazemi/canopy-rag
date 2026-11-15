# Note 3: the domain discovery report

Where we are: the report that closes the phase. Book: none. This note uses domain-driven design (DDD), which is also the proposal's first objective.
File made in this step: `docs/domain_discovery_report.md`.

## In one minute

Phase 1 produced separate pieces: scope, case study, glossary, registry, metrics and testing rules. The report joins them into one story that a supervisor can read in ten minutes, and it states what is still open. Its job is to make sure that everybody means the same thing before any code exists.

## 1. Domain-driven design in plain words

Analogy: a restaurant. The kitchen, the dining room and the cashier all use the word "order", but it means a list of dishes in the kitchen, a table's request in the dining room, and a bill to pay at the cashier. If the software uses one `Order` class for all three, it will be confusing. DDD says: give each area its own model and its own words, and write the words down.

| DDD word | Meaning | Example here |
|---|---|---|
| Domain | The real-world area the software is about | Organizational knowledge transfer |
| Ubiquitous language | One set of words used everywhere: meetings, documents, code | The glossary: 61 terms |
| Bounded context | A part of the domain with its own words and rules | RAG Core, Issue Management, Knowledge Transfer |
| Entity | A thing with an identity that stays the same | Node, Issue, TransferPackage |
| Value object | A thing defined only by its value | LayerIndex, JudgeThreshold |

An entity has an identity: two issues with the same title are still two issues. A value object has none: the number 18 is just 18. A concept in our glossary is a word the domain uses that is not a class yet.

## 2. Why the report exists

A report is where a gap shows. In writing it, we found that the glossary had no word for "metric" or "baseline" (we added them), that the metrics needed a place for targets that were not agreed yet (a placeholder, plus a rule that a number needs a source), and that the unit-testing page and the hard rules had to point at each other. Writing the whole story forces the pieces to agree.

## 3. How to read it

| Section | The question it answers |
|---|---|
| 1. Summary | What did Phase 1 produce? |
| 2. The domain | What is the system for, and what are the three ideas? |
| 3. The organization model | What does the organization look like, and what are the registry rules? |
| 4. The knowledge | What documents and problems does the case study hold? |
| 5. Objectives and scope | What must it achieve, and what is out? |
| 6. The shared vocabulary | Which words are fixed? |
| 7. How success is judged | Which numbers, and which rules? |
| 8. How the work is tested | What do tests cover, and what not? |
| 9. Risks and assumptions | What could go wrong? |
| 10. Decisions to confirm | What does the supervisor have to decide? |
| 11. Deliverables | Is Phase 1 done? |
| 12. Hand-off | What does Phase 2 receive? |

## 4. A five-minute talk for your supervisor

1. **The problem.** Knowledge sits in separate places, and reports upward lose facts. (Section 2.)
2. **The idea.** Each node answers from its own documents, reports upward in a judged summary, offline. (Section 2.)
3. **The test bed.** The city: 7 nodes, 20 documents, 26 questions with planted problems. (Sections 3 and 4.)
4. **How we will know it works.** 28 metrics and 10 hard rules, no targets until the baseline. (Section 7.)
5. **What we need from you.** The decisions in section 10.

## 5. Why a checker keeps the pieces in step

The same number lives in several places: the glossary has 61 terms in a CSV, in a Markdown page, in the README and in the report. People forget one of them. `tools/run_checks.py` compares them. This is the idea of a **single source of truth**: one place is the real one (the CSV), and every other place is checked against it. We tested the checker itself by breaking a copy of the project in 60 different ways, and every break was caught.

## 6. Common mistakes

1. Writing the report last and from memory, so it disagrees with the files.
2. Using two words for one thing ("domain" and "field of activity"). The glossary exists to stop this.
3. Hiding open decisions. A good report lists them.
4. Treating the case study as real data. It is a test bed, with problems planted on purpose.

## 7. Check yourself

1. What is the difference between an entity and a value object? Give one of each from the glossary.
2. Why does the report list "decisions to confirm" instead of making them?
3. Where does the number "45 terms" live, and which one is the source of truth?

Answers:

1. An entity keeps its identity over time (Node). A value object is only its value (LayerIndex).
2. They belong to the supervisor: the targets, the threshold of 18, the registry template, the term "terminal node".
3. In `glossary.csv`, `glossary.md`, the README and the report. The CSV is the source of truth, and the checker compares the others to it.
