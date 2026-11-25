# Ingestion prototype

Project: offline hierarchical RAG core. Source: Phase 4 of the project proposal (sections 7.2, 7.3 and 21). Status: built and run on the city; DOC, PDF and scanned PDF wait for tools you install. Date: 2026-11-01. Updated 2026-11-25: real DOCX and PDF files of the city, an image-only D19, and PDFs read page by page.

This is the main Phase 4 deliverable: a working prototype that registers DOC, DOCX and PDF files (and Markdown), extracts their text, records metadata and source locations, chunks them, and stores them. The code is in `rag_core/ingestion/`.

## The flow

```
file ──> detect the format from its bytes ──> pick the extractor ──> text + sections (headings or pages)
                                                     │
          PDF page with no text layer? ── yes ──> render that page ──> LVM reads it (glm-ocr)
                                                     │
     fingerprints (file, text) ──> same text as a version of this item? ── yes ──> skip (an exact repeat)
                                                     │ no
     metadata record (checked) ──> chunks with source locations ──> new item or new version ──> repository
```

Each step maps to the knowledge life cycle of the proposal (section 7.2): registration, metadata, file processing, text and structure extraction, chunking, version assignment. Embedding, duplicate detection and indexing (steps 6 to 8) come in Phases 5 and 8.

## What can be read

| Format | How | Needs | State on this laptop |
| --- | --- | --- | --- |
| Markdown, text | read as UTF-8; `#` headings make sections | nothing | ready |
| DOCX | the standard library opens the ZIP and reads `word/document.xml`: paragraphs, heading styles, tables | nothing | ready |
| PDF with text | pypdf reads each page; one section per page | `pip install pypdf` | ready (pypdf 6.21.4) |
| PDF page that is a scan | pypdfium2 renders that page, `png.py` (standard library) makes a PNG, the LVM reads it | `pip install pypdfium2`, Ollama running, `--ocr` | renderer ready (pypdfium2 5.14.0); the LVM needs Ollama |
| DOC (old Word) | LibreOffice converts it to DOCX in a temporary folder, then the DOCX reader | LibreOffice | waits for you |

`python -m rag_core extractors` prints this table for your laptop.

Format detection reads the first bytes: `%PDF-` is a PDF, `PK` plus `word/document.xml` is a DOCX, the OLE signature is an old DOC. A file whose name and bytes disagree is refused with a clear message. The common mistake is to trust the extension.

**PDF: text or scan, page by page.** A page with fewer than 5 words in its text layer has no real text layer: it is a scanned page. Each such page, and only that page, is rendered to a PNG and sent to the LVM through the `VisionModel` port; the other pages are read as text. Page numbers do not move, so every chunk and citation still names its page. The `extraction_method` says what happened: `pdf_text` (no page needed the LVM), `lvm_ocr` (every page did) or `pdf_mixed` (some did). Without an LVM, a PDF that is mostly scanned is refused with "start Ollama and pass --ocr"; a PDF with a few empty pages is read from its text, and a warning names the pages that were not read. The tests are in `tests/test_core_pdf_pages.py`, with a stub LVM from `rag_core/fakes.py`.

## The real files of the city (2026-11-25)

The Markdown files stay the source of truth. `scripts/make_real_files.py` uses LibreOffice (headless, it reads Markdown) to make five real files from them, in the same node folder and with the same file stem, so citations and the answer key do not change. The manifest names each one in two columns, `real_file` and `real_format`:

| Document | Node | real_format | Made how |
| --- | --- | --- | --- |
| D02 City Strategy 2030 | N0 | `pdf_text` | LibreOffice PDF export |
| D04 Transport Policy 2025 | N1 | `docx` | LibreOffice Word export |
| D13 Maintenance Schedule 2025 | N4 | `docx` | LibreOffice Word export |
| D17 Route 7 Pilot Test Report | N6 | `pdf_text` | LibreOffice PDF export |
| D19 Meeting Minutes 18 June 2025 | N6 | `pdf_image_only` | LibreOffice PDF, each page rendered to grey pixels (pypdfium2, 144 dpi), written back as pictures only by `rag_core/ingestion/image_pdf.py` (standard library; no Pillow) |

The D10 versions and the D12 duplicate stay Markdown, so the planted traps do not change. The script checks its output: each DOCX keeps its headings, each text PDF has a text layer, and the D19 PDF has none. `tools/run_checks.py` checks the manifest columns, that each real file sits beside its Markdown with the same stem, and that only the text PDFs name a font.

`ingest-case-study` reads the real files. Without `--ocr` there is no LVM, so D19 is read from its Markdown and the report says so in a note; with `--ocr` the image-only PDF goes to the LVM. `--markdown` reads only the Markdown files, as before. Library callers (`manifest_requests`) read the Markdown unless they pass `real_files=True`, so the Phase 2 runner and the Phase 5 experiment keep reading what they read before.

On 2026-11-25, without `--ocr`: 20 new items, 1 new version (D10 v2, active), 1 exact repeat skipped (the D12 copy), 0 failed. D02 and D17 give chunks on page 1; D04 and D13 give chunks with heading paths. A text PDF loses the Markdown table lines and list marks, so its text differs a little from the Markdown: ingest it in a new run (`--run-id`), or an older Markdown version with the same tag is refused under H04.

The project database keeps the copy of the manifest it was seeded with. A database seeded before 2026-11-25 has no `real_file` column, so `ingest-case-study` reads the Markdown and prints a note; point `RAG_DATA_DB` at a new file to read the real files.

## Results on the city (2026-11-01)

`python -m rag_core ingest-case-study --run-id phase4-words80`:

| Outcome | Files |
| --- | --- |
| new item | 20 |
| new version | 1 (D10 version 2; it became active, version 1 is kept) |
| skipped: exact repeat | 1 (the D12 copy: the same text as D12 version 3) |
| failed | 0 |

The results are in `results/ingestion/phase4-words80/`: `knowledge.sqlite` (the database), `catalog.csv` (one row per version), `chunks.csv` (one row per chunk with its source location), and `ingestion_report.csv` (one row per file and what happened). The same run with `--policy sections80` is in `results/ingestion/phase4-sections80/`.

Two planted problems are now handled at ingestion, before any model runs:

- **The version trap (D10).** Both versions are stored; version 2 is active, so retrieval will see only "135 buses". In Phase 2 both versions were in the index.
- **The duplicate (D12).** The copy is not indexed. In Phase 2 the model cited both files and M12 (duplicate cited once) was 0. That metric should be measured again once Phase 8 retrieval uses this index.

## Commands

Run from `UNI-Project/` with the project's Python (see `docs/operator_guide.md` for the `$py` variable):

```powershell
& $py -m rag_core extractors
& $py -I scripts\make_real_files.py
& $py -m rag_core ingest-case-study --run-id my-first-run
& $py -m rag_core ingest-case-study --run-id markdown-only --markdown
& $py -m rag_core make-samples
& $py -m rag_core ingest-case-study --documents results\ingestion\samples --suffix .docx --run-id docx-copies
& $py -m rag_core ingest-file case_study\documents\N6_bus_network_project\D19_meeting_minutes_2025-06-18.pdf --item D19 --node N6 --version 1 --title "Meeting Minutes 18 June 2025" --out results\ingestion\d19-scan --ocr
```

- `scripts/make_real_files.py` makes the five real files the manifest names (above) and checks them; `--check` only checks.
- `make-samples` writes DOCX and simple PDF copies of five documents into `results/ingestion/samples/`. They are made with the standard library, so they are simpler than files saved by Word or LibreOffice.
- `--documents ... --suffix .docx` ingests the converted copies where they exist and the Markdown files elsewhere. Use a new run id: a converted copy can differ slightly from the Markdown (a DOCX table has no `|---|` line), so in the same database it would be refused as new text under an old version tag (H04).
- By default, `ingest-file` and `ingest-case-study` read the live hierarchy and save knowledge in the project database. An explicit `--out` selects a separate run database. Pass `--hierarchy-db` to ingest against a separate hierarchy. The last example command reads the image-only D19 PDF described below.

## The image-only D19 PDF

The proposal's plan needs D19 as a scanned PDF, so the LVM is tested inside ingestion and not only on loose images (E4 used `results/inputs/d19_clean.png` and `d19_degraded.png`). Since 2026-11-25 it is `case_study/documents/N6_bus_network_project/D19_meeting_minutes_2025-06-18.pdf`, made by `scripts/make_real_files.py`. It is a clean render (no noise or tilt), so it is easier than a real scan; a degraded copy is still a manual step if you want one:

1. Open `results/inputs/d19_degraded.png` (made by `scripts/render_d19.ps1`) in the Windows Photos app.
2. Print it with the printer "Microsoft Print to PDF", and save it as `D19_meeting_minutes_2025-06-18.pdf` in a new folder such as `team/C/files/N6_bus_network_project/`.
3. Check it is image-only: open it and try to select text. Nothing should highlight.
4. Ingest it with `--ocr` as in the last command above (with the new path), into a fresh run.

## Not in this prototype

- Embeddings and the vector index (Phase 8). The database already holds every chunk with its node, ready to embed.
- Near duplicates and overlaps run only with `--detect-duplicates` and `find-duplicates` (Phase 5: `architecture/versioning_and_duplicates.md`).
- Tables inside PDFs: pypdf reads them as lines of text, and their columns may run together.
- Images inside DOCX files are skipped. The proposal allows the LVM for them (section 7.3); that is a later step.
