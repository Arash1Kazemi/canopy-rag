# Versioning, the chunk life cycle and duplicate detection

Project: offline hierarchical RAG core. Source: Phase 5 of the project proposal (sections 7.2, 7.6 and 7.7). Status: draft for supervisor review. Date: 2026-11-08.

This is a Phase 5 deliverable. The code is in `rag_core/knowledge/` (`changes.py`, `lifecycle.py`, `duplicates.py`), and the tests are `tests/test_core_changes.py`, `tests/test_core_lifecycle.py` and `tests/test_core_duplicates.py`.

## What Phase 5 adds to Phases 3 and 4

| Proposal task | Before Phase 5 | Phase 5 |
| --- | --- | --- |
| Knowledge version control | Versions never deleted (H04), one active (H03), sequence number, link to the previous version | Every new version also gets a **change summary** against the version registered before it |
| Chunk life cycle | Chunks were created at ingestion | **ChunkStage**: created, embedded, checked, indexed, and the rule for what retrieval may use |
| Exact duplicates | An exact repeat of an item's own version is skipped; the same text in another item is noted | The same check as a **DuplicateRecord** with its evidence |
| Near duplicates and overlap | not built | **DuplicateDetector** with a **DuplicatePolicy**, an experiment, and the `find-duplicates` command |
| Unit tests | 183 tests | 44 more |

## 1. The change summary

`summarize_change(old_text, new_text)` compares two texts word by word. It says how many words were added and removed, and shows the first eight changes. The same two texts always give the same note.

Real output for the City, D10 version 1 to version 2 (stored in `diff_summary` and written to `catalog.csv`):

```
27 words added, 8 removed in 8 place(s): '1' -> '2 (supersedes version 1)'; '15 January' -> '10 July';
added 'Reason for change: 15 new electric ...'; '80' -> '78'; '30' -> '32'; '10' -> '25'; '**120**' -> '**135**'; '9.4' -> '8.1'
```

The first version of an item has no change summary (the field is empty). A change summary is a help for a person, not a measure of how important the change is.

## 2. The chunk life cycle

```
created --> embedded --> checked --> indexed
   ^                                    |
   +------------- reset ----------------+   (embed again, for example after a new embedding model)
```

- A chunk moves one step at a time. Skipping a step or going back raises an error, except the reset to `created`.
- **Retirement is not a stage.** Retrieval may use a chunk only if it is `indexed` **and** its version is the item's active version. Switching the active version changes what is retrievable at once, and switching back needs no repair, because the old chunks are never altered (H04). `ChunkLifecycle.retrievable_chunks(item)` is this rule.
- The stages are kept in memory in Phase 5. Phase 8 builds the embedding and the index, and stores the stages with them (decision A12).

## 3. Duplicate detection

Three kinds of finding. A **DuplicateRecord** holds the kind, the two versions, a score, the number of shared word groups, whether the nodes are the same, and which compared metadata fields differ.

| Kind | Meaning | How it is decided |
| --- | --- | --- |
| exact | The same normalized text (same `ContentHash`) | Equal hashes. Score 1.0 |
| near | Almost the same words | **Resemblance** at or above `near_limit` |
| overlap | A part of one text sits inside the other | At least `min_shared_groups` shared word groups. The score reported is the **containment** |

In words:

- A **word group** is the words in a row, 5 by default. Words are lower-cased and punctuation is ignored, so a Markdown file and its DOCX copy give the same groups.
- **Resemblance** = the word groups found in both texts, divided by the word groups found in either. One means identical, zero means nothing shared.
- **Containment** = the word groups found in both texts, divided by the word groups of the smaller text. One means the smaller text sits entirely inside the other.
- The kinds are checked in order: exact, then near, then overlap. A pair gets at most one kind.

Rules of the detector:

1. Versions of one item are never compared with each other: they are meant to be similar (decision A14). D10 version 1 and version 2 are never a finding.
2. By default only the active versions are compared, because retrieval uses them. `all_versions=True` (or `--all-versions`) compares every version.
3. A pair is listed once, in a fixed order (by item id, then version tag).
4. A finding is advice for a person. Nothing is merged, hidden or deleted (decision A13).

### The policy numbers are starting values, not tuned

| Setting | Starting value | Where it comes from |
| --- | --- | --- |
| `word_group_size` | 5 | A common choice; try 3 and 8 in the experiment |
| `near_limit` | 0.8 | In the experiment, 2% of words replaced gives resemblance about 0.81 |
| `min_shared_groups` | 20 | Among the 190 pairs of different City documents the most shared groups was 2; 20 groups is a passage of 24 words |

`scripts/duplicate_experiment.py` measures how the measures behave on the City documents (they are only read). Results are in `results/duplicates/phase5-experiment/experiment.csv`. Word group size 5, one document (D18, 199 words), five random seeds:

| Test | Result |
| --- | --- |
| A. Different documents (190 pairs) | Highest resemblance 0.020, highest containment 0.087, at most 2 shared groups (D11 and D14) |
| B. 1% of words replaced | resemblance 0.894: near in 5 of 5 |
| B. 2% replaced | 0.812: near in 4, overlap in 1 (right at the limit) |
| B. 5% replaced | 0.600: overlap in 5 of 5 |
| B. 10% / 20% replaced | 0.381 / 0.149: overlap in 5 of 5 |
| B. 40% replaced | 0.025: no finding |
| C. A passage inside another document | 10 words: 5 shared groups, none. 20 words: 15, none. 40 words: 33, overlap. 80 and 133 words: overlap |
| D. Markdown written as DOCX and read back | resemblance 1.000 for group sizes 3, 5 and 8 |

What this shows, and does not show:

- Word groups are strict. One replaced word breaks up to 5 groups, so 5% of changed words already costs 40% of the resemblance. A copy with a few edited words is near; a copy with many edits is an overlap.
- A 2% edit sits right at the near limit, so a pair close to it can fall on either side. A person reviews the findings for this reason.
- The City documents are short (about 200 words) and were written to be different. A real archive has boilerplate (headers, standard clauses), which will produce overlaps that are not real duplicates. Measure again on real files before trusting the limits.
- The case study has one planted exact pair and one planted version pair. Metrics M10 (duplicate detection recall) and M11 (false duplicate alarms) need more planted pairs before they mean anything. M11 is met here only in the weak sense that the City gives 0 findings, including for D10 version 1 and 2 with `--all-versions`. No target is set.

### Not built in Phase 5

| Proposal method | Status |
| --- | --- |
| Hash comparison, text normalization | built (exact and near) |
| Similarity at the level of the knowledge chunk | not built: the word groups work on whole documents. Add it if an experiment shows that a copied section in a long document is missed |
| Similarity by embeddings | Phase 8 (it needs the embedding model) |
| Metadata comparison | built as evidence (`same_node`, `metadata_differences`) |
| Final check by the LLM in unclear cases | Phase 10 (it needs the judge) |
| Issues that are similar to earlier issues (section 7.7, last item) | Phase 7 |

Two limits to know. The scan compares every pair, so its cost grows with the square of the number of items; this is fine for hundreds of items, and MinHash (a way to compare short fingerprints) is the usual next step for thousands. And a finding names the other item even when it lives in another node: the scan is an administrator tool, not a node answer, so H01 does not apply, but keep this in mind before showing findings to node users.

## 4. How to use it

```bash
../.venv/bin/python.exe -m rag_core ingest-case-study --run-id phase5-words80 --detect-duplicates
../.venv/bin/python.exe -m rag_core find-duplicates --db results/ingestion/phase5-words80/knowledge.sqlite
../.venv/bin/python.exe -m rag_core find-duplicates --db results/ingestion/phase5-words80/knowledge.sqlite --all-versions
../.venv/bin/python.exe -I scripts/duplicate_experiment.py
```

With `--detect-duplicates`, a near duplicate or an overlap becomes a note in `ingestion_report.csv` and the file is still registered. A `duplicates.csv` is written next to the database. The default ingestion does not run the detector, so the Phase 4 results stay reproducible.

## 5. Decisions made in Phase 5

| # | Decision | Why |
| --- | --- | --- |
| A11 | Re-chunking an item with another policy is a new ingestion run into a new database. Stored versions are never edited | H04. It also keeps the `words80` and `sections80` runs apart for the E3 comparison |
| A12 | Chunk stages are kept in memory until Phase 8, and a chunk is retrievable only if it is indexed and its version is active | The embedding and the index do not exist yet; the stage belongs with them |
| A13 | Near duplicates and overlaps are findings for a person. Nothing is merged, hidden or deleted | A wrong automatic merge loses knowledge, and H04 forbids deleting a version |
| A14 | Detection compares different items only, and active versions by default | Versions of one item are meant to be similar; retrieval uses the active version |
| A15 | The starting policy is word groups of 5, near at resemblance 0.8, overlap at 20 shared groups | Chosen from the experiment above; not tuned |

All five are marked "to confirm" in `architecture/architecture.md`.

## 6. Tests

| File | What it checks |
| --- | --- |
| `test_core_changes.py` | The note for a changed number, an added or removed word, no change, the cap of eight changes, the cut after six words, and that the same input gives the same note |
| `test_core_lifecycle.py` | The stage order, no skipping and no going back, reset, untracked chunks, and what is retrievable, including switching the active version and back |
| `test_core_duplicates.py` | The measures in numbers, exact, near (layout only and one word changed) and overlap, a short shared phrase is no overlap, unrelated texts, versions of one item, active-only, order, metadata evidence, the City has no findings (M11), ingestion notes, the change summary at ingestion, SQLite and CSV, and the command |

As in Phases 3 and 4, each rule was broken on purpose to check that a test notices: 10 of 11 breaks were caught. The one not caught is turning difflib's `autojunk` shortcut on in the change summary; in 3,000 random long texts it gave the same result, so no test can separate the two settings.
