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
