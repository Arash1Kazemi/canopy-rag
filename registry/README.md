# Node and layer registry

One row per node. Layer 0 is the top; each node has at most one parent, and its layer is always its parent's layer plus 1.

| Column | Meaning |
|---|---|
| node_id | Stable id, never reused |
| name | Display name |
| layer_index | 0 = top of the organization |
| parent_node_id | The node this one reports to; empty only for the root |
| field_of_activity | The subject area the node works in, such as transport or water |
| is_terminal | true = black box, its internal structure is not modeled |
| reporting_format | Detail level used when this node sends a package to its parent: executive, managerial, technical_summary, or detailed_technical |
| min_judge_score | Minimum judge score (out of 20) a package needs before it is sent. 18 is the proposal's default; confirm with the supervisor |
| confidentiality | internal or confidential |

Detail gets coarser going up: layer 3 sends a technical summary, layer 2 a managerial one, layer 1 an executive one.

## The layer registry

`layer_registry.csv` has one row per layer: its name and role, and the transfer rule of the layer, which says what the layer needs from the nodes below it. A layer that receives nothing (the lowest one in the City) has an empty `detail_level` and no other rule fields. An empty rule field means "not decided yet"; it is never a default number.

| Column | Meaning |
|---|---|
| layer_index | 0 = top of the organization; one row for each layer the nodes use |
| name | The layer's name, such as Strategic layer |
| role | What kind of node sits in this layer (proposal section 6.2) |
| detail_level | The detail level this layer needs from the layer below: executive, managerial, technical_summary, or detailed_technical. Empty when the layer receives nothing |
| min_judge_score | Minimum judge score (out of 20) a package needs before it is sent to this layer. Empty = not decided |
| required_topics | Topics a package must cover, separated by `;` (the typical output of the detail level, proposal section 6.4) |
| excluded_topics | Topics a package must leave out, separated by `;`. Empty = not decided |
| required_fields | Fields a package must contain, separated by `;`. Empty = not decided |
| output_format | The preferred output format. Empty = not decided |
| max_words | The longest a package may be, in words. Empty = not decided |
| citation_level | short or long (see `architecture/citation_model.md`). Empty = not decided |
| source | Where the row's values come from |

A node's `reporting_format` and `min_judge_score` in the node registry repeat the rule of its parent's layer. `tools/run_checks.py` keeps them equal.
