# Note 12: real files and honest tests (Part A of the build)

Where we are: Part A of the build (revisiting Phases 1, 4, 5 and 6). Book: chapters 3, 4 and 8
Files: `case_study/heldout_questions.csv`, `tests/fixtures/duplicates/pairs.csv`, `scripts/make_real_files.py`, `rag_core/ingestion/` (per-page PDF reading), `rag_core/organization/directory.py`.

## In one minute

Part A did not add a big feature. It made the project more honest. We added questions we promise not to tune on, labelled pairs to measure duplicate detection, real Word and PDF files, and one place that answers "does this node exist?".

## 1. A held-out set: do not tune on your test set

**Analogy.** A student who gets the exam questions in advance. She scores 100 percent. That does not mean she knows the subject.

**Precise idea.** When you tune a system (change chunk size, a prompt, a threshold), you look at scores and keep what raises them. If you look at the same questions every time, you slowly fit the system to those questions. The score goes up, but it no longer tells you how the system does on new questions. A **held-out set** is a set of questions that no tuning step ever reads. You run it once, at the end. The book calls this keeping a test set separate (chapters 3 and 4).

**City example.** The answer key has 26 questions. We tune on them. `case_study/heldout_questions.csv` has 10 more (HQ01 to HQ10) on the same city. Nothing reads them until the end of Phase 14. If the 26 score well and the 10 score badly, we over-tuned.

**Common mistake.** "I will just peek once, to see how we are doing." One peek is enough. After that the set is no longer held out. Write the rule down and keep to it.

## 2. Labelled pairs, precision and recall

**Analogy.** A metal detector at the beach. You buried 8 coins and marked where. If it beeps on 3 of them, it found 3 out of 8. If it also beeps on 2 bottle caps, those are false alarms.

**Precise idea in words.**
- **Recall**: of the real duplicates, how many did we find? Found divided by planted.
- **Precision**: of the things we flagged, how many were real? Real divided by flagged.
- You can only measure them if you have **labels**: someone decided in advance which pairs are duplicates.

`tests/fixtures/duplicates/pairs.csv` holds 26 labelled pairs: exact copies, near copies (reworded), overlaps (one text inside another), and different pairs that must not be flagged.

**Real numbers (M10 and M11, run 2026-11-25, baselines and not targets):**

| Kind | Result |
| --- | --- |
| Exact copies | recall 1.000 (2 pairs) |
| Near copies | recall 0.375 (8 pairs) |
| Overlaps | recall 0.875 (8 pairs) |
| False alarms on different pairs | 0 (8 pairs) |

Near recall is low because our rule says "near" means 0.8 or more shared words. A reworded text shares fewer words than that, so it falls below 0.8 and is missed. The threshold 0.8 was an untuned starting value. The labels now let us see it. The fix is not to change the number blindly. Try other values on the labelled pairs, and watch the false alarms stay at 0.

**Common mistake.** Reporting "duplicate detection works" after testing the one pair you planted by hand (D12). With one pair, recall is 0 or 1. That tells you nothing.

## 3. Image-only PDFs and per-page routing

**Analogy.** Two kinds of paper. One is a typed page: you can copy the words. The other is a photo of a page: it looks the same, but there is no text to copy. You need a reader (OCR) for the photo.

**Precise idea.** A PDF may have a **text layer** (the words are stored as text) or be **image-only** (each page is a picture). Reading the text layer is fast and exact. Reading an image needs the vision model, which is slower and can make mistakes. A PDF can also **mix** both: some pages typed, some scanned. So we decide **per page**, not per file. For each page: if it has text, read the text; if not, send that page to the vision model. The code marks this `pdf_mixed`. Citations keep the page number either way.

**City example.** D19 is an image-only PDF. `python -m rag_core ingest-case-study --ocr` sends each page to the vision model. D02 and D17 are text PDFs, so the vision model is not used. `scripts/make_real_files.py` builds all of these from the Markdown, so we can repeat it.

**Common mistake.** Checking only the first page, or only the file, and then treating a mixed PDF as text. Pages without text silently become empty and the answers disappear.

## 4. Why the node directory beats string checks

**Analogy.** A phone book. To know if "N6" is a real person, look it up. Do not guess from the shape of the name.

**Precise idea.** Before, code could check a node id by its text ("starts with N"). That accepts `N99`, which does not exist, and says nothing about whether the node is terminal. The **node directory** (`rag_core/organization/directory.py`) answers two questions from the real hierarchy: `exists(node_id)` and `is_terminal(node_id)`. `require` returns the node or raises `UnknownNodeError`. Issues and retrieval call it, so the rule lives in one place.

**City example.** Creating an issue in `N99` is refused because the directory does not know it. Asking whether N3 (Housing) is terminal gives yes, so nothing can be placed under it.

**Common mistake.** Copying a "valid node" check into each module. Later the hierarchy changes (a node moves or becomes terminal) and the copies disagree.

## Questions for you

1. Why must the 10 held-out questions stay unread until the end?
2. Near recall is 0.375 and false alarms are 0. If you lower the threshold from 0.8, what would you expect to happen to each, and why?
3. A PDF has 3 typed pages and 2 scanned pages. Why is a per-file rule wrong?
