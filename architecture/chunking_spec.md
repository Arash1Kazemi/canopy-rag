# Chunking specification

Project: offline hierarchical RAG core. Source: Phase 4 of the project proposal (section 7.4). Status: draft for supervisor review. Date: 2026-11-01.

This is a Phase 4 deliverable. The code is `rag_core/knowledge/chunking.py`, and its tests are in `tests/test_core_chunking.py`.

## Why chunk at all

A small model reads a short context well and a long one badly, and a retriever finds a precise piece more easily than a whole file. The proposal adds two more reasons: a chunk can be cited precisely, and duplicates are easier to compare piece by piece (section 7.4). Chapter 6 of the book covers chunking for RAG.

## The policies

| Policy | Words per chunk | Overlap | Crosses a heading or a page | Status |
| --- | --- | --- | --- | --- |
| `words80` | 80 | 15 | yes | default: the Phase 2 baseline |
| `sections80` | 80 | 15 | no; small neighbouring sections are packed together up to 80 words | available, not yet measured |

**How a window moves.** The first chunk takes words 1 to 80. The next starts 65 words later (80 minus the 15-word overlap), so its first 15 words repeat the last 15 of the chunk before. The last chunk reaches the end of the text. A text of 80 words or fewer is one chunk. This is exactly the Phase 2 stepping, and a unit test checks that `words80` gives the same chunk texts as `baseline_runner/chunking.py` for all 22 case-study files, so the Phase 2 results stay comparable.

**Sections.** The extractor reports sections: a Markdown or DOCX heading starts one, and each PDF page is one. `sections80` keeps every chunk inside one group of sections. Neighbouring small sections are joined while the group stays at or under 80 words. A long section is cut into windows as above.

## What every chunk keeps

The proposal lists six things a chunk must keep (section 7.4). All six are stored:

| The proposal asks for | Stored as |
| --- | --- |
| the source document id | `SourceLocation.item_id` and `source_file` |
| the version id | `SourceLocation.version_tag` |
| the page or section reference | `page_start`, `page_end` (PDF), and `heading_path` |
| the heading path | `heading_path`, such as ("Bus Fleet Inventory", "Fleet by type") |
| metadata inherited from the item | the version's MetadataRecord; each chunk also carries its `node_id` |
| the order and context boundaries | `order` (1, 2, 3 ...), and `char_start`, `char_end` in the extracted text |

The chunk id is `item@version#order`, for example `D10@2#1`.

## Rules the tests check

1. No word of the text is lost.
2. No chunk is longer than the policy's limit.
3. Neighbouring chunks overlap by exactly the policy's overlap.
4. The character span of a chunk points at exactly its words in the extracted text.
5. `sections80` never puts words from two sections that do not fit together in one chunk.
6. A policy whose overlap is as big as its chunk is refused.

## The city in numbers (2026-11-01)

| Policy | Chunks of active versions | Words per chunk: smallest / middle / largest | Chunks with a heading path |
| --- | --- | --- | --- |
| words80 | 33 | 16 / 69 / 80 | 33 |
| sections80 | 34 | 15 / 53 / 80 | 34 |

From `results/ingestion/phase4-words80/` and `results/ingestion/phase4-sections80/`. The two policies give almost the same number of chunks because the city documents are short. `sections80` chunks are smaller in the middle, because they stop at headings.

## Known weak spot

With `words80`, the last window of a text can be short and mostly overlap. For example D01 has 81 words, so its second chunk has 16 words, and 15 of them repeat the end of the first chunk. A short tail is harmless for retrieval quality on its own, but it can push a useful chunk out of the top 3. Measuring that is part of the experiment below.

## Next: the experiment that decides the default

Run E3 (the end-to-end answers) with both policies and compare M01 (answer correctness), M07 (context precision) and M08 (context recall). Change the default only if `sections80` is at least as good on all three. Until then the default stays `words80` (decision A8 in `architecture/architecture.md`).
