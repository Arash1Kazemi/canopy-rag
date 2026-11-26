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
| `documents/` | 22 Markdown files = 20 documents (D01 to D20) + 1 older version + 1 exact duplicate, and 5 real DOCX and PDF files made from 5 of them |
| `documents_manifest.csv` | One row per Markdown file: node, language, version, planted problem, and the real file made from it (`real_file`, `real_format`) |
| `issues.csv` | 7 issues, 3 of them sub-issues of I01 |
| `people.csv` | 6 executors with expertise |
| `ike_seed_relations.csv` | 38 IKE relations (Phase 9) taken from the files above: 15 stated by `issues.csv` and `people.csv`, 23 stated clearly by a document (named in `evidence`) |
| `answer_key.csv` | 26 test questions with expected answers and sources; each is answerable from the one node named in `asked_at_node` |

## Problems planted on purpose

| Problem | Where | What it tests later |
|---|---|---|
| Exact duplicate | D12 and its _copy | Duplicate detection |
| New version | D10 v1 (120 buses) vs v2 (135 buses) | Versioning, active version |
| Contradiction | D11 says Route 12 busiest; D16 says Route 7 (both in N6) | Research gaps, honest uncertainty |
| Scanned PDF | D19 (its real file is an image-only PDF) | Extraction, vision model |
| Node boundary | D07 belongs to N2; Q22 asks N6 about it | Metadata filtering |
| Terminal nodes | N3, N5 | Black-box boundary |
| Unanswerable | Q23, Q24 | Saying "insufficient knowledge" |

## Formats
The Markdown files are the source of truth, so you can edit them easily. The proposal ingests DOC, DOCX and PDF, so
`scripts/make_real_files.py` uses LibreOffice to make real files from five of them, in the same node folder and with
the same file stem (so citations and the answer key do not change):

| real_format | Documents | How it is read |
|---|---|---|
| `docx` | D04, D13 | the DOCX reader (headings and tables) |
| `pdf_text` | D02, D17 | pypdf, one section per page |
| `pdf_image_only` | D19 | no text layer: each page goes to the vision model (`--ocr`) |

After editing one of these five Markdown files, run the script again. `python -m rag_core ingest-case-study` reads the
real files; `--markdown` reads only the Markdown. Without `--ocr` there is no vision model, so D19 is read from its
Markdown and the report says so. The D10 versions and the D12 duplicate stay Markdown on purpose. No DOC file is made:
the DOC reader is tested with a stand-in for LibreOffice.

## Held-out questions

`heldout_questions.csv` has 10 new questions (`HQ01` to `HQ10`) about the same city, with the same columns as `answer_key.csv`. The ids start with `HQ` because `H01` to `H10` are the hard rules. Every question is answerable only from the node that asks it, or is planted as `unanswerable` or `node_boundary`. None repeats a question of the answer key.

This file is held out. No tuning step may read it: not the baseline runner, not retrieval or prompt experiments, not any script that picks a setting. It is run once, at the end of Phase 14, to get an honest final score. The book says the same (Ch. 3 and 4): do not tune on your test set. A test (`tests/test_core_heldout.py`) fails if any Python file under `rag_core/`, `baseline_runner/` or `scripts/` mentions the file name.
