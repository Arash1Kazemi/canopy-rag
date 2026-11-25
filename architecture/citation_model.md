# Citation model

Project: offline hierarchical RAG core. Source: Phase 4 of the project proposal ("define the source citation model", section 21) and sections 7.3 and 7.4. Status: draft for supervisor review. Date: 2026-11-01.

This is a Phase 4 deliverable. The code is `rag_core/rag/citation.py`, tested in `tests/test_core_citation.py`.

## The idea

Every claim in an answer must point to where it came from (H09). A citation has two forms:

| Form | Example | For |
| --- | --- | --- |
| short | `[D10_bus_fleet_inventory_v2]` | the answer text; the grading rules GR4 and GR5 read it |
| long | `[D19_meeting_minutes_2025-06-18, p. 1, Minutes > Decisions, chunk D19@1#2]` | a person checking the answer |

The short form is the file stem: the file name without folder and extension. It is what Phase 2 used, so the grading rules and their results stay valid. The long form adds what the chunk knows: the pages, the heading path and the chunk id.

## How a citation is made

1. Retrieval returns chunks. Each chunk has a SourceLocation (item, version, file, pages, heading path, character span).
2. `Citation.of_chunk(chunk)` turns it into a citation.
3. The answer prompt shows each chunk with its short form, and the model is told to cite it in square brackets (prompt P01).
4. `parse_citations(answer)` reads the stems back out of the answer. `[A, B]` counts as two citations; text in brackets that is not a stem, such as `[the report above]`, is ignored.

## Rules

1. A cited stem must belong to a chunk that was given to the model, and to the asking node (checked by GR5 now, and by the answer formatter in Phase 8).
2. An old version is never cited by default, because retrieval uses only active versions. The version is in the stem (`..._v2`) and in the chunk id (`D10@2#1`).
3. A duplicate is cited once (GR4). Since ingestion skips an exact repeat, the D12 copy is no longer in the index at all, so it cannot be cited.
4. A page is shown only when the format has pages (PDF). A Markdown or DOCX file shows its heading path instead. A PDF page read by the LVM keeps its page number too. Checked from file to citation in `tests/test_core_pdf_pages.py` (a two-page PDF with one scanned page) and `tests/test_core_real_files.py` (the real D02, D17 and D19 PDFs of the city).

## Why not cite chunk ids in the answer

A chunk id such as `D10@2#1` is precise, but a small model copies long, similar ids badly, and the Phase 2 grading works on stems. The answer cites the stem; the system keeps the mapping from the answer back to the chunks it used, so the long form can always be shown.
