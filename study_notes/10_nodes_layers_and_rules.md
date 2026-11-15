# Note 10: nodes, layers and the layer registry (Phase 6)

Where we are: Phase 6. Book: not in the book (domain modelling). Chapter 10 gives the overall picture of an AI system, and the layer rules feed the transfer packages of Phase 11.
Files: `architecture/hierarchy_and_layers.md`, `registry/layer_registry.csv`, and the code in `rag_core/organization/`, `rag_core/workflows/` and `rag_core/infrastructure/sqlite_hierarchy.py`.

## In one minute

Phase 3 built the tree of nodes and its two rules (one root, and no children under a terminal node). Phase 6 makes the tree **usable and changeable**: each layer gets a name and a rule for what it needs from the layer below, and nodes can be added, moved and made terminal through workflows that refuse anything that would break a rule.

## 1. A node's layer follows from its parent

**Analogy.** Floors in a building. You decide which team a unit reports to, and the floor follows: one floor below that team. You never say "put it on floor 3".

**Precise idea.** H02 says a node is one layer below its parent. So the workflows take a **parent** and no layer. To put a node in layer 3, give it a parent in layer 2.

**Common mistake.** Storing the layer as a free choice next to the parent. The two can then disagree. Here the layer is checked against the parent every time.

## 2. The rule belongs to the layer that receives

**Analogy.** A manager's inbox rules. The manager says what they want to read ("a one-page summary, with risks and decisions needed"). Each team writes to fit the manager, not the other way round.

**Precise idea.** A layer's **transfer rule** says what it needs from the layer below: the detail level, the minimum judge score, the topics, and more. In the City, layer 0 (the Strategic layer) needs *executive* packages, so N1, N2 and N3 send executive packages to N0.

## 3. Two copies of one fact, kept equal

The node registry already had `reporting_format` on each node. The layer rule says the same thing from the receiving side. Two copies can drift apart. So:

- The **rule is the source**. The node's value is a copy.
- A new node must match the rule, or it is refused.
- When a node **moves**, its copy is recomputed from the rule of its new parent's layer.
- When a rule **changes**, the nodes that send into that layer are updated.
- The checker compares the two files and fails if they disagree.

**Example.** The Bus Network Project (N6) sends a technical summary to the Transit Agency. Move it under the Water Dept (a layer-1 node). Now its layer is 2, and it sends what layer 1 asks for, so the workflow says: `N6: layer 3 -> 2, now sends managerial instead of technical_summary`.

**Common mistake.** Letting a person edit the copy by hand. It would silently disagree with the rule, so the node refuses that edit and says to change the rule instead.

## 4. Moving a node

A move carries the node's whole subtree with it, and every node in it shifts by the same number of layers. These are refused:

| Move | Why |
| --- | --- |
| the root | there is no layer above it to move into |
| under itself or one of its own descendants | the tree would loop |
| under a terminal node | H10: a terminal node has no children |
| under the parent it already has | nothing to do |
| under a layer that has no transfer rule | it could not receive packages |

A refused move changes nothing, and the workflow saves nothing.

## 5. A terminal node: two halves again

Note 08 said H10 has two halves with two owners. Phase 6 shows it when a node *becomes* terminal later. The tree half (no children) is checked by `Hierarchy`. The document half (one summary document) needs the knowledge repository, so the workflow checks it. If either fails, nothing is saved.

## 6. "Not decided yet" is not zero

The proposal lists things a layer rule *can* define (excluded topics, required fields, output format, maximum length, citation level) but gives no values. We left them **empty**. An empty field means "ask the supervisor". A default would look like a decision nobody made. `python -m rag_core show-hierarchy` prints what is still undecided for each layer.

## Questions

1. Why does `define-node` take a parent and not a layer?
2. Layer 1 asks for managerial packages and layer 2 asks for technical summaries. You try to change the rule of layer 1 to detailed technical. What happens, and why?
3. Why does the make-terminal workflow need the knowledge database, when `Hierarchy` already knows its children?

## Answers

1. Because the layer is always the parent's layer plus one (H02). Asking for both would let them disagree. With only a parent, there is nothing to get wrong.
2. It is refused and nothing changes. Layer 1 would then ask for more detail than layer 2, but detail must get coarser going up (executive at the top, then managerial, technical summary, detailed technical at the bottom). `set_layer_rule` checks the whole registry after the change and puts everything back if a rule is broken.
3. Because the second half of H10 (one summary document) is about the node's documents, which the hierarchy does not hold. The workflow reads the knowledge repository to count them.
