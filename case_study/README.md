# Case study: the City (fictional)

A small made-up city government used to test the system.

## The tree

```
N0 City Council (layer 0)
├── N1 Transport Dept (layer 1)
│   └── N4 Transit Agency (layer 2)
│       └── N6 Bus Network Project (layer 3)
├── N2 Water Dept (layer 1)
│   └── N5 Water Utility (layer 2, terminal)
└── N3 Housing Dept (layer 1, terminal)
```

Terminal nodes (N3, N5) have one summary document each; their insides are not modeled.

**Rule used everywhere:** a node answers only from the documents stored in its own folder.

## What is in this folder

| File | Purpose |
|---|---|
| `documents/` | 22 files = 20 documents (D01 to D20) + 1 older version + 1 exact duplicate |
| `documents_manifest.csv` | One row per file: node, language, version, planted problem |
| `issues.csv` | 7 issues, 3 of them sub-issues of I01 |
| `people.csv` | 6 executors with expertise |
| `answer_key.csv` | 26 test questions with expected answers and sources; each is answerable from the one node named in `asked_at_node` |

## Problems planted on purpose

| Problem | Where | What it tests later |
|---|---|---|
| Exact duplicate | D12 and its _copy | Duplicate detection |
| New version | D10 v1 (120 buses) vs v2 (135 buses) | Versioning, active version |
| Contradiction | D11 says Route 12 busiest; D16 says Route 7 (both in N6) | Research gaps, honest uncertainty |
| Scanned PDF | D19 (convert to image-only PDF yourself) | Extraction, vision model |
| Node boundary | D07 belongs to N2; Q22 asks N6 about it | Metadata filtering |
| Terminal nodes | N3, N5 | Black-box boundary |
| Unanswerable | Q23, Q24 | Saying "insufficient knowledge" |

## Formats
The files are Markdown so you can edit them easily. The proposal ingests DOC, DOCX and PDF, so in Phase 4 we will convert
some of them (all three formats) with a small script. D19 should become an image-only PDF.

## Held-out questions

`heldout_questions.csv` has 10 new questions (`HQ01` to `HQ10`) about the same city, with the same columns as `answer_key.csv`. The ids start with `HQ` because `H01` to `H10` are the hard rules. Every question is answerable only from the node that asks it, or is planted as `unanswerable` or `node_boundary`. None repeats a question of the answer key.

This file is held out. No tuning step may read it: not the baseline runner, not retrieval or prompt experiments, not any script that picks a setting. It is run once, at the end of Phase 14, to get an honest final score. The book says the same (Ch. 3 and 4): do not tune on your test set. A test (`tests/test_core_heldout.py`) fails if any Python file under `rag_core/`, `baseline_runner/` or `scripts/` mentions the file name.
