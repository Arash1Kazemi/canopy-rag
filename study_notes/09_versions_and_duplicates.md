# Note 9: versions, the chunk life cycle and duplicates (Phase 5)

Where we are: Phase 5. Book: chapter 8 (deduplication) and chapter 6 (chunks and retrieval).
Files: `architecture/versioning_and_duplicates.md`, and the code in `rag_core/knowledge/` (`changes.py`, `lifecycle.py`, `duplicates.py`). The deeper guide is `guides/rag.html`, section 8.

## In one minute

Documents change and get copied. Phase 5 gives the system three answers: **what changed** between two versions (the change summary), **what may be retrieved** right now (the chunk life cycle), and **which documents repeat each other** (duplicates, near duplicates and overlaps). The last one only gives advice: a person decides.

## 1. The change summary

**Analogy.** The "what's new" note at the top of an app update.

**Precise idea.** When a new version of an item arrives, the system compares its text with the version registered before it, word by word, and stores a short note in `diff_summary`. It says how many words were added and removed, and shows up to eight changes. The first version has no note.

**Example.** D10 version 2 against version 1: `'**120**' -> '**135**'`, `'80' -> '78'` and six more changes.

**Common mistake.** Reading the note as "how important the change is". It only counts and shows words. A changed comma and a changed bus count look the same size.

## 2. The chunk life cycle

**Analogy.** A parcel in a sorting office: it is received, scanned, checked, and put on the shelf. A customer can only be handed a parcel that is on the shelf, and only from the current edition.

**Precise idea.** A chunk goes through four stages, one step at a time: `created`, `embedded`, `checked` (for duplicates), `indexed`. It can be sent back to `created` to be embedded again, for example with a new embedding model. A chunk is **retrievable** only if it is `indexed` **and** its version is the item's active version.

**Why "retired" is not a stage.** If retiring were a stage, switching the active version back would need every chunk repaired. With the rule above, switching the active version changes what is retrievable at once, and switching back changes it back. Nothing was ever altered (H04).

**Common mistake.** Letting old versions answer because they are still in the index. Keeping them is right (for history); answering from them is not.

## 3. Word groups: how to tell that two texts are almost the same

A **word group** is the words in a row. With groups of 3 words, "the fleet has 135 buses" has three groups: *the fleet has*, *fleet has 135* and *has 135 buses*.

Take the same sentence with 120 instead of 135. Its groups are *the fleet has*, *fleet has 120* and *has 120 buses*. Only one group is shared.

- **Resemblance** = shared groups divided by all the different groups in either text. Here 1 shared out of 5 different groups in total, so 0.2. In words: how much of everything they say is the same.
- **Containment** = shared groups divided by the groups of the smaller text. Here 1 out of 3, so 0.33. In words: how much of the smaller text is found inside the other.

One changed word broke up to 3 groups out of 3. This is why the measure is strict, and why the experiment (`scripts/duplicate_experiment.py`, groups of 5) found that 5% of changed words already drops resemblance to about 0.6.

| Kind | Meaning | In the code |
| --- | --- | --- |
| exact | The same text after whitespace cleanup | Same hash |
| near | Almost the same words | Resemblance at or above 0.8 (a starting value) |
| overlap | A part of one text sits inside the other | At least 20 shared groups, about a 24-word passage (a starting value) |

**Common mistakes.**

1. Trusting the limits (5, 0.8, 20). They are starting values from a small set of short, planted documents. Measure again on real files.
2. Comparing versions of one item. They are meant to be similar, so D10 version 1 and 2 are never a finding.
3. Merging automatically. A wrong merge loses knowledge, so a finding is advice.
4. Using a ratio alone for overlap. A copied section inside a long document has a small ratio but many shared groups, so the count decides.

## Questions

1. Why is "retired" not a chunk stage?
2. Two texts differ in one word out of 200. Roughly what is the resemblance with groups of 5, and is it near?
3. Why does the detector never compare version 1 and version 2 of D10?

## Answers

1. Because retrievable is decided by two facts (indexed, and the version is active). Switching the active version then changes what is retrievable at once and needs no repair when it is switched back.
2. One changed word breaks up to 5 groups out of about 196, so about 191 shared out of 201 different groups in total: roughly 0.95. That is above 0.8, so it is near.
3. Versions of one item are meant to be similar, so comparing them would flag every update as a duplicate (metric M11 counts such false alarms).
