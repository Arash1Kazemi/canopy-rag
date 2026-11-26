# Open questions for the supervisor

One line per question, with a link to where it comes from. Take this to the meeting. Nothing here is decided yet.

## Metrics and judging

- What are the targets for the 28 metrics? Every target reads `to agree with supervisor`, and a number needs a `target_source`. Source: [metrics/metrics.csv](../metrics/metrics.csv), [metrics/metrics.md](../metrics/metrics.md).
- Is the judge threshold of 18 out of 20 right, and is it the same for every layer? It is the proposal's default. Source: [docs/final_report.md](final_report.md), [docs/domain_discovery_report.md](domain_discovery_report.md).

## Phase 1 choices

- Is the node and layer registry template acceptable (7 nodes, 4 layers)? Source: [registry/README.md](../registry/README.md), [registry/node_layer_registry.csv](../registry/node_layer_registry.csv).
- Do we keep the term "terminal node" (a node treated as a black box with one summary document)? It is not in the proposal. Source: [glossary/glossary.md](../glossary/glossary.md) (Decisions to confirm).

## Glossary: decisions to confirm

- "Proposal": we write "project proposal" for the document and "RFP response" for the entity, and the class stays `Proposal`. Is that fine? Source: [glossary/glossary.md](../glossary/glossary.md).
- "Issue": one class with a type field instead of five classes (problem, question, need, research gap, operational concern). Is that fine? Source: [glossary/glossary.md](../glossary/glossary.md).
- "Executor": keep it as in the proposal, so it includes organizational capabilities and not only people. Is that fine? Source: [glossary/glossary.md](../glossary/glossary.md).
- "Hierarchy": the whole tree of one organization's layers and nodes, as an entity named Organizational Hierarchy that guards the tree rules. Is that fine? Source: [glossary/glossary.md](../glossary/glossary.md).
- Detail level names: executive, managerial, technical summary, detailed technical, for the proposal's four levels. Are these the right English names? Source: [glossary/glossary.md](../glossary/glossary.md).
- "Test double": an engineering word kept in Evaluation and Judging, because no proposal context owns it. Is that fine? Source: [glossary/glossary.md](../glossary/glossary.md).

## Architecture decisions marked "To confirm: yes"

Source for all of these: [architecture/architecture.md](../architecture/architecture.md), section 10.

- A2: Is SQLite the right local database (built in, one file, offline)?
- A4: Is it right that the newest version by natural tag order becomes active, and an older one registered late does not?
- A6: Is it right that an exact repeat of a version's text is skipped at ingestion (the D12 copy), while near duplicates and overlaps are only advice?
- A8: Is it right to keep `words80` as the default chunking until `sections80` is measured?
- A9: Is it right that rule H10 ("one summary document" for a terminal node) is checked in the ingestion use case?
- A10: May new glossary classes come from proposal text or be added by us when a phase needs them?
- A11: Is re-chunking with another policy a new ingestion run into a new database, with stored versions never edited?
- A12: Are chunk stages kept in memory until Phase 8, and is a chunk retrievable only if it is indexed and its version is active?
- A13: Are near duplicates and overlaps findings for a person only, with nothing merged, hidden or deleted?
- A14: Does duplicate detection compare different items only, and active versions by default?
- A15: Are the starting policy numbers acceptable (word groups of 5, near at 0.8, overlap at 20 shared groups)? They are not tuned. See also [architecture/versioning_and_duplicates.md](../architecture/versioning_and_duplicates.md).
- A16: Does the transfer rule belong to the receiving layer, with a node's reporting format and minimum score copied from its parent's layer? See also [architecture/hierarchy_and_layers.md](../architecture/hierarchy_and_layers.md).
- A17: May a node move to a new parent with its whole subtree, and are moves under itself, a descendant or a terminal node refused?
- A18: Are nodes never deleted and ids never reused, with retiring a node left for later?
- A19: Do the registry CSV files only seed a hierarchy database, which is the truth after that?
- A20: Do excluded topics, required fields, output format, maximum length and citation level stay empty until you decide their values?

## Added during the build (A21+)

- A21: the held-out set is run once, at the end of Phase 14. [architecture.md section 10](../architecture/architecture.md)
- A22: duplicate pair labels are human judgements; exact means same text after whitespace. [architecture.md section 10](../architecture/architecture.md)
- A23: an unknown node id raises an error, it is never "not terminal". [architecture.md section 10](../architecture/architecture.md)
- A24: the Markdown stays the source of truth; real files are extra manifest columns (`real_file`, `real_format`). [architecture.md section 10](../architecture/architecture.md)
- A25: five real files: DOCX D04 and D13, text PDF D02 and D17, image-only PDF D19; no .doc; D10 and D12 stay Markdown. [architecture.md section 10](../architecture/architecture.md)
- A26: D19 is a clean render with no scan noise, so it is easier than a real scan. Is that acceptable? [architecture.md section 10](../architecture/architecture.md)
- A27: with no vision model, D19 falls back to its Markdown with a note; a PDF with a few empty pages warns, not fails. [architecture.md section 10](../architecture/architecture.md)
- A28: a PDF page has no text layer when it has fewer than 5 words (untuned). [architecture.md section 10](../architecture/architecture.md)
- A29: pages are rendered at 144 dpi in grey for the vision model (untuned). [architecture.md section 10](../architecture/architecture.md)
- A30: the ten issue statuses of 14.1 and the table of allowed moves between them; old values map by meaning. [architecture.md section 10](../architecture/architecture.md)
- A31: progress from the seven factors of 14.1 with untuned weights adding to 100; only a solved issue shows 100. [architecture.md section 10](../architecture/architecture.md)
- A32: priority is not set, low, medium or high; category is free text. Which priority scale do you want? [architecture.md section 10](../architecture/architecture.md)
- A33: sub-issues and blocked-by links stay inside one node, with no cycles. [architecture.md section 10](../architecture/architecture.md)
- A34: a draft is compared with its own node's issues by shared words; no threshold until labelled issue pairs exist. [architecture.md section 10](../architecture/architecture.md)
- A35: LLM sub-issue suggestions are saved only after a person accepts them, all in one transaction. [architecture.md section 10](../architecture/architecture.md)
- A36: issues live in `data/project.sqlite`; `case_study/issues.csv` is imported once, keeping ids and parents. [architecture.md section 10](../architecture/architecture.md)
- A37: A node searches only its own chunks, not its parent's or its descendants'. [architecture.md section 10](../architecture/architecture.md)
- A38: Only chunks of active versions are embedded; old vectors may stay in the index and retrieval filters them out. [architecture.md section 10](../architecture/architecture.md)
- A39: The vector index is the durable record of the `indexed` chunk stage; stages are rebuilt from it after a restart, and `checked` blocks nothing. [architecture.md section 10](../architecture/architecture.md)
- A40: Exact cosine search over all eligible vectors, ties broken by chunk id. [architecture.md section 10](../architecture/architecture.md)
- A41: Embedding batch size 16 (untuned) and default k = 3 (the Phase 2 baseline). [architecture.md section 10](../architecture/architecture.md)
- A42: A metadata filter means "equal", except `tags`, which means "is one of the labels". [architecture.md section 10](../architecture/architecture.md)
- A43: Tokens are estimated as the larger of words x 1.5 and characters / 3; there is no tokenizer in the core. [architecture.md section 10](../architecture/architecture.md)
- A44: An answer with no valid citation becomes "Insufficient knowledge." by default (`uncited_policy=refuse`); `mark` keeps it and flags it. [architecture.md section 10](../architecture/architecture.md)
- A45: Context is filled in rank order and stops at the first chunk that does not fit; no chunk is cut; `min_score` has no default. [architecture.md section 10](../architecture/architecture.md)
- A46: Indexing, retrieval and answering live in `rag_core/rag/` as pure use cases that take their ports as arguments; prompt files are loaded in `rag_core/workflows/`. [architecture.md section 10](../architecture/architecture.md)
- A47: Answer prompt P13 (v2) adds a conflict rule (report both documents) and "cite only files shown"; P01 stays the default until both are compared on the 26 questions. [architecture.md section 10](../architecture/architecture.md)
- A48: the Phase 2 runner gets `e3 --engine core`; the full move of the grading code into the core is left for Phase 14. [architecture.md section 10](../architecture/architecture.md)
- A49: `evaluate` reads the Markdown files and differs from the baseline in three known ways (active versions only, checked citations, an uncited answer is a refusal). [architecture.md section 10](../architecture/architecture.md)
- A50: the comparison baseline is `results/e3-first` (regraded), M05 is not measured before Phase 10. [architecture.md section 10](../architecture/architecture.md)
- A51: a setup problem exits with code 2 and a refusal exits with 0; `evaluate` never overwrites a run. [architecture.md section 10](../architecture/architecture.md)
- A52: Executor matching looks only in the issue's own node by default; scope "lineage" (ancestors and descendants) is opt-in. [architecture.md section 10](../architecture/architecture.md)
- A53: An executor can be mapped to an issue only from the issue's node lineage, never from another branch. [architecture.md section 10](../architecture/architecture.md)
- A54: The match score has four components (tags 60, documents 25, same node 15, availability 0), all untuned. [architecture.md section 10](../architecture/architecture.md)
- A55: The tag share is the coverage of the executor's own tags, and a candidate needs at least one matched tag or document. [architecture.md section 10](../architecture/architecture.md)
- A56: "Author", "Project lead" and "Prepared by" lines in a document count as writing or owning it; attendee lists do not. [architecture.md section 10](../architecture/architecture.md)
- A57: Executor kinds are person, team, unit and capability; `people.csv` holds persons only. [architecture.md section 10](../architecture/architecture.md)
- A58: Mapping an executor does not change the issue status to "executor identified"; that stays a separate action. [architecture.md section 10](../architecture/architecture.md)
- A59: Executors and IKE relations in terminal nodes are allowed. [architecture.md section 10](../architecture/architecture.md)
- A60: Each IKE relation type allows exactly one source kind and one target kind. [architecture.md section 10](../architecture/architecture.md)
- A61: An "answer" in an IKE relation is an issue's answer or probable solution (12.5), keyed by the issue id. [architecture.md section 10](../architecture/architecture.md)
- A62: "Similar" has no direction and is stored once; a duplicate relation is the same type, source and target. [architecture.md section 10](../architecture/architecture.md)
- A63: Issues, answers and knowledge items stay in their own node; an executor may appear in another node's relation, but its expertise and project edges belong to its own node. [architecture.md section 10](../architecture/architecture.md)
- A64: Decomposes-into and blocked-by relations never form a cycle, and a sub-issue has one parent. [architecture.md section 10](../architecture/architecture.md)
- A65: `Issue.parent_issue_id` and `Issue.blocked_by` own those links; the IKE edges mirror them and are not synced automatically. [architecture.md section 10](../architecture/architecture.md)
- A66: The IKE seed (`case_study/ike_seed_relations.csv`, 38 relations) holds only relations stated in the records or a named document. [architecture.md section 10](../architecture/architecture.md)
- A67: The M15 and M16 rubrics (`metrics/rubrics/`) use one rater, and a claim with no support scores at most 2. [architecture.md section 10](../architecture/architecture.md)
