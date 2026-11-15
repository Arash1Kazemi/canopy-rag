# Nodes, layers and the layer registry

Project: offline hierarchical RAG core. Source: Phase 6 of the project proposal (sections 6.1 to 6.4 and 10.1). Status: draft for supervisor review. Date: 2026-11-08.

This is a Phase 6 deliverable. The code is in `rag_core/organization/model.py` (the `Hierarchy` aggregate), `rag_core/shared/kernel.py` (`TransferRule`), `rag_core/workflows/organization.py` (the workflows) and `rag_core/infrastructure/` (`registry_csv.py`, `sqlite_hierarchy.py`). The data is `registry/layer_registry.csv`. The tests are `tests/test_core_hierarchy.py`, `tests/test_core_layer_registry.py` and `tests/test_core_workflows.py`.

## What Phase 6 adds to Phase 3

| Proposal task | Before Phase 6 | Phase 6 |
| --- | --- | --- |
| Node definition | `add_node`; nodes came only from the registry CSV | A **define node** workflow, with errors that say which rule was broken |
| Layer registry | Layers were only an index and a list of nodes | A **layer registry**: each layer has a name, a role and a transfer rule (`registry/layer_registry.csv`) |
| Parent and child relations | parent, children, path | Also ancestors, descendants, siblings, nodes in a layer, terminal nodes, and **move a node** |
| Terminal-node boundary | "no children" and "one document" at creation | Both halves also hold **when a node becomes terminal later** |
| Transfer needs of each layer | `reporting_format` and `min_judge_score` copied on each node | A **TransferRule** per layer; the nodes' values are kept equal to it |

## 1. Layer membership

A node's layer is never chosen: it is the parent's layer plus one (H02). To put a node in layer 3, you give it a parent in layer 2. That is why the workflows take a parent and no layer.

## 2. The layer registry

`registry/layer_registry.csv` has one row per layer. The columns are in `registry/README.md`.

| Layer | Name (proposal 6.2) | Receives | Minimum judge score |
| --- | --- | --- | --- |
| 0 | Strategic layer | executive packages | 18 |
| 1 | Parent organizations | managerial packages | 18 |
| 2 | Subsidiaries and specialist units | technical summary packages | 18 |
| 3 | Projects, teams and executing nodes | nothing (no layer is below it in the City) | none |

Where the values come from:

- The **names and roles** are the proposal's layer types (section 6.2).
- The **detail level** of each layer is what the registry already said its children send: N1, N2 and N3 send executive packages to N0, N4 and N5 send managerial packages to N1 and N2, and N6 sends a technical summary to N4.
- The **required topics** are the "typical output" of each detail level in the proposal's table in section 6.4 (for example, managerial: project status, issue status, research gaps, decisions needed, resource needs, RFP or proposal status).
- The **score 18** is the proposal's default and is marked "to confirm".
- **Everything else is left empty on purpose:** excluded topics, required fields, output format, maximum length and citation level. The proposal lists them as things a layer *can* define (section 10.1) but gives no values, so an empty field means "not decided yet" and never a default number. `python -m rag_core show-hierarchy` lists what is not decided for each layer.

## 3. The transfer rule belongs to the receiving layer

Proposal section 6.3 says each layer decides what it needs from the layers below. So the `TransferRule` is stored on the layer that **receives** the package. A node's `reporting_format` and `min_judge_score` in the node registry are a copy of the rule of its parent's layer.

The aggregate keeps the copy equal to the rule (decision A16):

- A new node must send what the rule of its parent's layer asks for, or it is refused.
- When a node moves, it and everything under it get the values of the rule that now receives them.
- When a layer's rule changes, the nodes that send into that layer get the new values.
- A node's `reporting_format` cannot be edited on the node while a rule sets it: change the rule.
- If the rule leaves the minimum score undecided, the node's own score stays free.
- `Hierarchy.problems()` lists every disagreement as a sentence, and `tools/run_checks.py` checks the same thing on the files. A rule may not ask for more detail than the layer below it (detail gets coarser going up).

## 4. The workflows

All five are methods of `OrganizationService`. Each loads the hierarchy, changes it through the aggregate, checks it is consistent, and saves it only then. A workflow never raises for a broken rule: the result says what went wrong and nothing is saved, so a bad request cannot leave the stored hierarchy half changed.

| Workflow | Needs | What it checks |
| --- | --- | --- |
| Define a node | id, name, parent, field of activity | The parent exists and is not terminal (H10), the id is new, the layer is the parent's plus one (H02), and the reporting values come from the parent layer's rule |
| Move a node | node, new parent | Not the root, not under itself or one of its own descendants, not under a terminal node (H10), not the same parent, and the new parent's layer can receive packages. The whole subtree moves and shifts layers by the same amount |
| Make a node terminal, or open it again | node (and the knowledge database to make it terminal) | No children (the tree half of H10) and at most one knowledge item (the document half) |
| Change a node | name, field of activity, confidentiality (and reporting values where no rule sets them) | The id, layer and parent do not change here |
| Define a layer, set a layer's rule | index, name, rule | The registry stays consistent, or nothing changes |

A move, from a real run on the City (the Bus Network Project goes from the Transit Agency to the Water Dept):

```
node moved: N6 is now under N2. N6: layer 3 -> 2, now sends managerial instead of technical_summary
```

Moving it under N5 is refused: `failed: H10: N5 is a terminal node and cannot have the child N6`.

## 5. The terminal-node boundary, both halves

| Half of H10 | Owner | Checked when |
| --- | --- | --- |
| A terminal node has no children | `Hierarchy` | adding a node (`add_node`), moving a node under it, making a node terminal |
| A terminal node has one summary document | the ingestion use case, and the make-terminal workflow | registering a second item in a terminal node, and making a node with two or more items terminal |

The second half spans two aggregates, so the workflow (an application service) reads the knowledge repository. The hierarchy context never imports the knowledge context, which would turn the context map around.

## 6. Storage

`SqliteHierarchyRepository` keeps the hierarchy in a SQLite file so nodes and layer rules can change while the system runs (decision A19). `python -m rag_core init-hierarchy` copies the two registry CSV files into it. After that the database is the truth; the CSV files are the reviewed starting point. `save` replaces the stored hierarchy in one transaction, and a hierarchy that does not pass `check_complete` is never saved. Foreign keys are on, so the database itself refuses a node with an unknown parent.

## 7. Commands

```bash
../.venv/bin/python.exe -m rag_core show-hierarchy
../.venv/bin/python.exe -m rag_core init-hierarchy --db results/hierarchy/hierarchy.sqlite
../.venv/bin/python.exe -m rag_core define-node --id N7 --name "Depot Upgrade" --parent N4 --field depots
../.venv/bin/python.exe -m rag_core move-node --id N6 --parent N2
../.venv/bin/python.exe -m rag_core set-terminal --id N7 --knowledge-db results/ingestion/phase5-words80/knowledge.sqlite
```

Without `--db`, `show-hierarchy` reads the CSV files, and the other commands use `results/hierarchy/hierarchy.sqlite`. The knowledge database in the last command is read only to count the documents of the node.

## 8. Decisions made in Phase 6

| # | Decision | Why |
| --- | --- | --- |
| A16 | The transfer rule belongs to the receiving layer. A node's reporting format and minimum score copy the rule of its parent's layer, are re-derived when the node moves, and a check keeps them equal | One source of truth for what a layer needs; the node columns stay for the registry file |
| A17 | A node can move to a new parent. Its whole subtree moves and shifts layers. The root, a move under itself or a descendant, and a move under a terminal node are refused | H02 and H10 stay true after every change |
| A18 | Nodes are never deleted, and an id is never reused. Retiring a node is a later decision, only if the case study needs it | The proposal asks for no deletion; knowledge belongs to a node |
| A19 | The registry CSV files seed a hierarchy database (`init-hierarchy`). After that the database is the truth | Nodes must be able to change at run time without editing a reviewed file |
| A20 | Only the detail level, the minimum judge score and the topics from proposal section 6.4 are filled in. Excluded topics, required fields, output format, maximum length and citation level stay empty until the supervisor decides | No invented values. The proposal lists five groups of required fields (issue status, research gap, achievement, project completion, RFP); one list holds them for now |

All five are marked "to confirm" in `architecture/architecture.md`.

## 9. Not built in Phase 6, and limits

- **No node deletion or history.** A node that is no longer used stays in the tree (A18). The database holds the current tree only, and the events a change produces are not stored.
- **A move does not move knowledge.** An item belongs to one node for good (ingestion refuses to change it), so moving a node changes where it sits, not what it owns.
- **Visibility limits** (proposal 6.1) are only the two confidentiality levels so far. What a node may see of another node's knowledge is decided with retrieval in Phase 8 (H01 already keeps a node to its own documents).
- **The optional layer 4** (internal knowledge sources) has no row, because the City has four layers. A fifth row can be added with `define_layer`.
- **The packages themselves**, and the AI suggestions that improve a rule (proposal 10.2), are Phase 11.
- A layer whose rule leaves the minimum score undecided lets each node set its own; that is on purpose, and it shows in `problems()` only if a node and a decided rule disagree.

## 10. Tests

| File | What it checks |
| --- | --- |
| `test_core_hierarchy.py` | The queries; moves (subtree, layer shift, reporting values re-derived, seven refused moves that change nothing); terminal nodes; node details; layer definitions, rule matching and the registry problems; changing a layer rule and rolling it back |
| `test_core_layer_registry.py` | The `TransferRule` checks; the City layer registry and what stays empty; a node that disagrees with its layer rule stops the load; rows to rules and back; the SQLite hierarchy: round trip, stored changes, no save of an inconsistent hierarchy, foreign keys, and a failed save that leaves the old hierarchy |
| `test_core_workflows.py` | Each workflow, including refusals that save nothing, both halves of H10, no raised errors, and the five commands |

On 2026-11-08 seventeen rules were broken in the code and six in the layer registry file, one at a time, and every one was caught (by a failing test, or by `tools/run_checks.py` for the file). The code and the file were then restored and everything passed.
