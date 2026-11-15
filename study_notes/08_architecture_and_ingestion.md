# Note 8: the architecture (Phase 3) and ingestion (Phase 4)

Where we are: Phases 3 and 4. Book: chapter 6 (chunking for RAG) and chapter 8 (deduplication). The architecture part is domain-driven design, which the book does not cover.
Files: `architecture/architecture.md`, `architecture/domain_model.md`, `architecture/unit_test_plan.md`, `architecture/ingestion.md`, and the code in `rag_core/`.

## In one minute

Phase 3 drew the map of the code before building it: ten bounded contexts, and inside each one an aggregate that guards its rules. Phase 4 built the first real use case on that map: ingestion. A file comes in, its format is detected from its bytes, its text is extracted, it gets a metadata record and chunks that know where they came from, and it is stored as a new item or a new version. Two planted problems (the old D10 version and the D12 copy) are now handled before any model runs.

## 1. Aggregates: one guard per group of rules

**Analogy.** A bank account. You never change the balance directly; you call "deposit" or "withdraw", and the account refuses to go below zero. The account is the guard of its rule.

**Precise idea.** An aggregate is a group of objects that change together, reached only through one root object. The root checks the rules on every change. `KnowledgeItem` is the root for its versions: `add_version` refuses a reused tag (H04), and there is no method to delete a version at all.

**Simple example.** `item.add_version(version("1", "other text"))` on an item that already has version 1 raises `DomainError("H04: ...")`.

**Realistic example.** D10 version 1 says 120 buses and version 2 says 135. Both are stored; version 2 is active (H03). If version 1 arrives after version 2, it is stored but does not become active, because "2" is newer than "1" in natural order.

```python
item = KnowledgeItem.register("D10", "N4", v1)
item.add_version(v2)              # v2 becomes active, v1 is kept
str(item.active_tag)              # "2"
```

**Common mistake.** Putting a rule in the place that is easiest to write instead of the object that can see everything the rule needs. "A terminal node has one summary document" talks about a node and all its items, so no single item can check it; the ingestion use case does (decision A9).

## 2. Layers and the dependency rule

**Analogy.** An onion. The rules are the core. Files, the database and Ollama are the outer skin. The core never reaches out to the skin; the skin is handed in.

**Precise idea.** The domain imports only the standard library. A use case receives its repository, its models and its clock as arguments. So a unit test can hand in an in-memory repository and a stub LVM, and run with the network off. `tests/test_core_architecture.py` reads the imports of every domain file and fails if one breaks the rule.

**Realistic example.** The same unit tests run against `InMemoryKnowledgeRepository` and `SqliteKnowledgeRepository` (`tests/test_core_storage.py`). Both pass, so the use case does not care which one it gets.

**Common mistake.** Calling the database or the model from inside an entity "because it is quicker". Then every test needs a database or a model, and the tests stop being unit tests.

## 3. Detect the format from the bytes

Every PDF starts with `%PDF-`. A DOCX is a ZIP file that contains `word/document.xml`. An old DOC starts with a fixed 8-byte signature. Reading these first bytes is called sniffing. A file named `report.docx` that is really a PDF is refused with a clear message. The common mistake is to trust the extension.

## 4. A DOCX file is a ZIP of XML

Rename a `.docx` to `.zip` and open it: inside is `word/document.xml`, where each paragraph is a `<w:p>` element and the text is in `<w:t>` elements. So the standard library can read DOCX with no download. Headings are paragraphs whose style is "heading 1", "heading 2" and so on.

## 5. Text PDF or scan?

A PDF can hold real text (a text layer) or only pictures of pages (a scan). pypdf reads the text layer. If a PDF gives fewer than 5 words per page, it is treated as a scan: each page is rendered to an image, and the LVM (glm-ocr, chosen in Phase 2) reads it. That is the proposal's "assistance of a local LVM when needed" (section 7.3).

## 6. Chunks that know where they came from

Each chunk keeps its item, version, file, pages, heading path and character span, the six things the proposal asks for (section 7.4). That is what makes a precise citation possible later.

The default chunking stays the Phase 2 baseline (80 words, 15 overlap), and a unit test proves the chunk texts are identical to Phase 2, so old results stay comparable. A second policy, `sections80`, never crosses a heading. Whether it is better is a question for an experiment, not for opinion (`architecture/chunking_spec.md`).

## 7. Fingerprints catch exact repeats

A SHA-256 hash turns any content into 64 characters; the same content always gives the same 64 characters. Ingestion stores two: one of the file's bytes and one of the normalized text (whitespace runs made into one space). The D12 copy has the same text fingerprint as D12, so it is skipped and never indexed. Chapter 8 of the book covers deduplication; exact matching is its simplest form. Near duplicates (almost the same text) are Phase 5: see study note 09.

## Questions

1. Why is there no `remove_version` method on `KnowledgeItem`?
2. A file is named `minutes.pdf` but starts with `PK`. What does ingestion do, and why is that better than trusting the name?
3. Why does the default chunking stay `words80`, even though `sections80` sounds smarter?

## Answers

1. Because of H04: an update adds a version and never deletes one. Not having the method makes the rule impossible to break by accident, which is stronger than checking it.
2. It refuses the file, saying the name and the bytes disagree (a ZIP is not a PDF). Trusting the name would send it to the PDF reader, which would fail in a confusing way or read nothing.
3. `words80` is the measured baseline. Changing it without measuring would make the next results impossible to compare with Phase 2. `sections80` becomes the default only if an experiment shows it is at least as good on M01, M07 and M08.
