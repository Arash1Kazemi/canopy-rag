# Ingestion prototype

Project: offline hierarchical RAG core. Source: Phase 4 of the project proposal (sections 7.2, 7.3 and 21). Status: built and run on the city; DOC, PDF and scanned PDF wait for tools you install. Date: 2026-11-01.

This is the main Phase 4 deliverable: a working prototype that registers DOC, DOCX and PDF files (and Markdown), extracts their text, records metadata and source locations, chunks them, and stores them. The code is in `rag_core/ingestion/`.

## The flow

```
file ──> detect the format from its bytes ──> pick the extractor ──> text + sections (headings or pages)
                                                     │
          PDF with no text layer? ── yes ──> render pages ──> LVM reads each page (glm-ocr)
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
| PDF with text | pypdf reads each page; one section per page | `pip install pypdf` | waits for you |
| PDF that is a scan | pypdfium2 renders each page, `png.py` (standard library) makes a PNG, the LVM reads it | `pip install pypdfium2`, Ollama running, `--ocr` | waits for you |
| DOC (old Word) | LibreOffice converts it to DOCX in a temporary folder, then the DOCX reader | LibreOffice | waits for you |

`python -m rag_core extractors` prints this table for your laptop.

Format detection reads the first bytes: `%PDF-` is a PDF, `PK` plus `word/document.xml` is a DOCX, the OLE signature is an old DOC. A file whose name and bytes disagree is refused with a clear message. The common mistake is to trust the extension.

**PDF: text or scan?** If a PDF has fewer than 5 words per page on average, it has no real text layer, so it is treated as a scan and goes to the LVM. A PDF that mixes text pages and scanned pages is a known gap: today it is read as text, and the scanned pages come out empty. Phase 5 can test page by page.

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
& $py -m rag_core ingest-case-study --run-id my-first-run
& $py -m rag_core make-samples
& $py -m rag_core ingest-case-study --documents results\ingestion\samples --suffix .docx --run-id docx-copies
& $py -m rag_core ingest-file team\C\files\N6_bus_network_project\D19_meeting_minutes_2025-06-18.pdf --item D19 --node N6 --version 1 --title "Meeting Minutes 18 June 2025" --out results\ingestion\d19-scan --ocr
```

- `make-samples` writes DOCX and simple PDF copies of five documents into `results/ingestion/samples/`. They are made with the standard library, so they are simpler than files saved by Word. Real files from Word or LibreOffice are still needed (Teammate C).
- `--documents ... --suffix .docx` ingests the converted copies where they exist and the Markdown files elsewhere. Use a new run id: a converted copy can differ slightly from the Markdown (a DOCX table has no `|---|` line), so in the same database it would be refused as new text under an old version tag (H04).
- `ingest-file` adds one file to the database in `--out` (a new one is made if the folder is empty), for example a new version of an item. The last command reads the image-only D19 PDF described below.

## The image-only D19 PDF

The proposal's plan needs D19 as a scanned PDF, so the LVM is tested inside ingestion and not only on loose images (E4 used `results/inputs/d19_clean.png` and `d19_degraded.png`). The tool to make it is not here, because it is a step for you to learn:

1. Open `results/inputs/d19_degraded.png` (made by `scripts/render_d19.ps1`) in the Windows Photos app.
2. Print it with the printer "Microsoft Print to PDF", and save it as `D19_meeting_minutes_2025-06-18.pdf` in a new folder such as `team/C/files/N6_bus_network_project/`.
3. Check it is image-only: open it and try to select text. Nothing should highlight.
4. Ingest it with `--ocr` as in the last command above, into a fresh run.

## Not in this prototype

- Embeddings and the vector index (Phase 8). The database already holds every chunk with its node, ready to embed.
- Near duplicates and overlaps run only with `--detect-duplicates` and `find-duplicates` (Phase 5: `architecture/versioning_and_duplicates.md`).
- Tables inside PDFs: pypdf reads them as lines of text, and their columns may run together.
- Images inside DOCX files are skipped. The proposal allows the LVM for them (section 7.3); that is a later step.
