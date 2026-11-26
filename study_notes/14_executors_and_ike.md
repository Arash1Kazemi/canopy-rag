# Note 14: executors and IKE (Phase 9)

Where we are: Phase 9. Book: chapter 6 (knowledge as structured data around RAG) — the proposal's section 13 has no direct chapter.
Files: `rag_core/executors/` (model, matching), `rag_core/workflows/executors.py`, `rag_core/ike/` (model, rules, seed, summary), `rag_core/workflows/ike.py`, `rag_core/cli_executors.py`, `case_study/ike_seed_relations.csv`, `config/executor_match_weights.csv`, `metrics/rubrics/`.
Decisions: A52 to A67 in `architecture/architecture.md`.

## In one minute

Phase 8 finds text. Phase 9 finds people and links. An **executor** is someone (or something) that can work on an issue. We match executors to issues with a score that shows its reasons. **IKE** is a small map of typed arrows: this issue needs that document, this person knows that topic. No model is used. It is plain code and plain data.

## 1. The idea: a staffing board and a map of who-knows-what

**Analogy.** Think of the board in an office where each person has a card: name, node, topics they know, documents they wrote. When a new issue arrives, the manager looks through the cards and says "Maryam, because she wrote the pilot report and she plans routes". The reason matters more than the name. Next to the board is a wall map. Each pin is an issue, a document, or a person. Each string between pins has a label: "depends on", "is blocked by", "has expertise in". That wall map is IKE.

**Precise idea, part 1: the score.** An executor carries **expertise tags**, short phrases like "route planning". To match an issue, we take its words (title, description, field of activity, category), remove stopwords, and ask four small questions. Each answer is a share from 0 to 1. Each share is multiplied by a weight, and the points are added. The weights add up to 100, so the score is from 0 to 100.

| Part | Question | Weight (untuned) |
| --- | --- | --- |
| tags | How much of the executor's tags do the issue's words cover? | 60 |
| documents | Did the executor write a document whose title shares a word with the issue? | 25 |
| same node | Does the executor live in the issue's node? | 15 |
| availability | Is the executor free? (not in the data yet) | 0 |

In words: a score is a bill with line items. You can read each line and argue with it.

**Precise idea, part 2: the 12 relation types.** An IKE relation is one typed arrow: a source, a target, a type, the node it belongs to, and the evidence or basis for it. The proposal names twelve types, for example "issue decomposes into issue", "issue is blocked by issue", "issue relates to knowledge", "issue lacks knowledge", "executor has expertise", "executor can follow issue". Each type allows only one kind of source and one kind of target (A60). So "executor has expertise" cannot point from an issue to an issue.

## 2. One example from the City: issue I01

I01 is "Route 7 overcrowded at peak", in node N6. Run `match-executors --issue I01`. P01 (Maryam Nazari) scores **70 of 100**:

| Part | Points | Why |
| --- | --- | --- |
| tags | 30 | Two tags: "route planning" shares "route", "bus intervals" shares "bus". Each tag is half covered, so the share is 0.5, and 0.5 x 60 = 30 |
| documents | 25 | She wrote D15 (Route Redesign Pilot Proposal) and D17 (Route 7 Pilot Test Report). Both titles share "route" |
| same node | 15 | She is in N6 and so is the issue |
| availability | 0 | Weight is 0, and the data has no availability |

30 + 25 + 15 + 0 = 70. The other people of N6 have no matching tag or document, so they are not listed. A candidate needs at least one reason (A55).

For the map, `ike-seed` loads 38 relations that the records or a named document already state, for example "I01 decomposes into I02, I03, I04" (from `issues.csv`) and "P01 has expertise route planning" (from `people.csv`). `ike-summary --node N6` prints the N6 part: counts by type, every edge, which issues have which knowledge, and who can follow up.

```python
# the heart of the score, in a few lines
def score(issue_words, executor, weights):
    tag_share = mean(len(issue_words & words(t)) / len(words(t)) for t in executor.tags)
    doc_share = 1 if any(issue_words & words(d.title) for d in executor.documents) else 0
    same_node = 1 if executor.node == issue.node else 0
    return weights.tags * tag_share + weights.documents * doc_share + weights.same_node * same_node
```

The real code keeps every part and the words that made it, so nothing is hidden.

## 3. The common mistakes

- **A score without reasons.** "P01: 70" is a number nobody can check. A reader cannot tell if it is luck. Always keep the parts and the matched words next to the number.
- **Treating the score as a measurement.** The weights 60, 25, 15 are starting values, not tuned (A54). The list is for a person to read, not for a machine to decide.
- **Inventing relations the data does not state.** It is tempting to add "P03 has worked on I01" because it sounds right. The seed holds only what a record or a named document says (A66). Past projects and availability are not in the data, so they stay empty.
- **Syncing by hand.** The issue owns its parent and its "blocked by" links. The IKE edges mirror them but are not synced automatically (A65). If you change one, the other can go stale.
- **Crossing nodes.** Matching looks only in the issue's own node by default. `--scope lineage` adds the ancestors and descendants. Siblings and cousins are never candidates (A52, A53).

## 4. Try it (no model needed)

```powershell
& $py -m rag_core match-executors --issue I01
& $py -m rag_core match-executors --issue I01 --scope lineage
& $py -m rag_core ike-seed
& $py -m rag_core ike-summary --node N6
```

## 5. Questions for you

1. Why does the score keep the matched words next to each part? What can go wrong without them?
2. P03 (data analyst, N6) is not listed for I01. Which two things would have to be true for P03 to appear?
3. You find a report that says "Reza worked on the 2024 fleet audit". Can you add an "executor worked on project" relation? What do you need first?
