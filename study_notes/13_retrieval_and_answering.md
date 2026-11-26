# Note 13: retrieval and answering (Phase 8)

Where we are: Phase 8. Book: chapter 6 (and chapter 5 for the prompt).
Files: `rag_core/rag/` (vector_index, indexing, retrieval, context, answering, citation), `rag_core/workflows/question_answering.py`, `rag_core/infrastructure/ollama_embedding.py`, `rag_core/cli_rag.py`, `rag_core/evaluation.py`, `prompts/answer_with_citations_v1.txt` and `_v2.txt`.
Decisions: A37 to A51 in `architecture/architecture.md`.

## In one minute

A question goes in. The system finds the few chunks of text that are closest to it, inside one node only. It puts them in a prompt, asks the model, and then checks that every citation points to a chunk it really gave. If nothing fits, it says "Insufficient knowledge."

## 1. The idea: a librarian who may only search one room

**Analogy.** A librarian works in a building with seven rooms. Each room is a node. You ask a question in room N6. The librarian may only walk the shelves of room N6. She picks the three books that look closest to your question, reads the right pages aloud, and tells you which book each fact came from. If room N6 has no answer, she says so. She does not walk into room N2, even if the answer is there.

**Precise idea.** Four steps:

1. **Embedding.** A model turns a piece of text into a list of numbers (a vector). Texts with a similar meaning get lists that point in a similar direction.
2. **Cosine similarity.** To compare two lists, we measure the angle between them. Same direction: score near 1. Unrelated: near 0. In words: "do these two arrows point the same way?" Length does not matter, only direction.
3. **Filter before rank.** First we throw away every chunk the question may not see: other nodes, old versions. Only then do we score and sort what is left, and keep the best k (we use k = 3).
4. **Context budget and citation check.** The model has a limited window (4096 tokens in the baseline). We fill it with chunks, best first, and never cut a chunk in half. After the model answers, we check every `[file stem]` it wrote against the chunks it was given. A citation to anything else is removed.

```python
# the heart of it, in a few lines
def retrieve(question_vector, chunks, node, k=3):
    allowed = [c for c in chunks if c.node == node and c.is_active]   # filter first
    scored = [(cosine(question_vector, c.vector), c) for c in allowed]  # then score
    return sorted(scored, key=lambda s: -s[0])[:k]                      # then rank
```

## 2. Three examples from the City

| Question | Node | What the design guarantees |
| --- | --- | --- |
| Q22: the allowed chlorine residual in drinking water | N6 | The answer lives in N2. N6 never sees N2's chunks, so no chunk of N2 reaches the model. The answer is "Insufficient knowledge." Asked at N2, the same question finds the chlorine fact, which shows the refusal is the node boundary and not a bad search. |
| Q01: how many buses now | N4 | Only the active version of D10 is searched. The context holds the table with 135, never the old one with 120. If the model writes a citation to the old file, the check removes it. |
| Q06: which route is the busiest | N6 | D11 says Route 12 and D16 says Route 7. The context holds both documents. Prompt P01 does not tell the model what to do about a conflict, so the Phase 2 baseline failed here. Prompt P13 adds a rule: report both, each with its file. Whether P13 helps is a measurement, not a guess (decision A47). |

## 3. The common mistakes

- **Filtering after ranking.** If you take the top 3 of all chunks and then drop the ones from other nodes, you may be left with 0 or 1. Worse, the foreign chunk already took a place and was scored. Filter first.
- **Trusting citations unchecked.** A small model can write `[D10_bus_fleet_inventory_v1]` because the name sounds right. A citation is only worth something if it names a chunk that was in the prompt. We check, and we remove the rest. An answer with no valid citation left becomes a refusal (decision A44).
- **Calling a metric better when the setup changed.** The core run is not the same experiment as Phase 2: it indexes only active versions, so the D12 copy is gone and Q03 can no longer cite both files. Say that when you compare.
- **Putting a number in code because it feels right.** `min_score` (a cut-off for weak chunks) has no default. A number needs a source.

## 4. How to use it

```
python -m rag_core index --db results\phase8\knowledge.sqlite
python -m rag_core ask --db results\phase8\knowledge.sqlite --node N6 "Which route is the busiest?"
python -m rag_core evaluate --run-id phase8-core-p01
```

`ask` prints the retrieved chunks with their scores, the answer, the checked citations (with pages and headings), and the reason if it refused. `evaluate` runs the 26 questions with the Phase 2 settings and prints a table against the baseline, with "not measured" where a number is missing. The exact steps and what to look for are in `docs/operator_guide.md`, part F. They are prepared and not run yet.

Add `--fake-models` to test the pipeline with no model. That checks the wiring and nothing about answer quality.

## 5. Where the book fits

- Chapter 6: retrieval, chunking, the context window, why retrieval quality limits answer quality. Our M06 to M08 measure retrieval alone, and M01 to M04 measure the whole path.
- Chapter 5: the prompt. P01 and P13 are two versions of one instruction. Compare prompts on the same 26 questions, change one thing at a time.
- Our context window is small because the laptop is small (4 GB of GPU memory). The budget matters here even where a bigger model would not need it.

## Questions for you (one at a time)

1. Why do we filter by node before ranking, and not after? Answer with the Q22 example.
2. The model answers Q01 with `120 buses [D10_bus_fleet_inventory_v1]`. What does the system do with that citation, and why is it safe to do it?
3. After the real run, M02 (citation validity) goes up and M04 (false refusal) also goes up. Give one reason that could explain both at the same time.
