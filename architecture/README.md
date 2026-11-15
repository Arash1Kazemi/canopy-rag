# architecture/

The design of the core, from Phase 3 on. The code that follows it is `rag_core/`.

| File | Phase | What it is |
| --- | --- | --- |
| `architecture.md` | 3 | The DDD architecture document: contexts, context map, layers, which object owns which hard rule, storage, decisions |
| `domain_model.md` | 3 | The domain model specification: every entity, value object and aggregate, built and planned |
| `unit_test_plan.md` | 3 | The first unit-test plan: test areas, files, doubles, and what comes in which phase |
| `ingestion.md` | 4 | The ingestion prototype: flow, formats, results on the city, commands |
| `metadata_schema.md` | 4 | The metadata schema, explained |
| `metadata_fields.csv` | 4 | The same schema as a table (a unit test keeps it equal to the code) |
| `chunking_spec.md` | 4 | The chunking specification |
| `citation_model.md` | 4 | The citation model |
| `versioning_and_duplicates.md` | 5 | The change summary, the chunk life cycle, duplicate and overlap detection, the experiment, decisions A11 to A15 |
| `hierarchy_and_layers.md` | 6 | The layer registry, the transfer rule of each layer, the node and layer workflows, the terminal-node boundary, decisions A16 to A20 |

The study notes for these phases are `study_notes/08_architecture_and_ingestion.md`, `study_notes/09_versions_and_duplicates.md` and `study_notes/10_nodes_layers_and_rules.md`.
