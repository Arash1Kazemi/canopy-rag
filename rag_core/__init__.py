"""The offline hierarchical RAG core (from Phase 3 on).

Layers, from the inside out (an inner layer never imports an outer one):

    shared/, organization/, knowledge/, rag/   domain: the rules, plain Python, no files, no network
    models/                                    ports: what the core needs from a local model
    ingestion/                                 application: use cases that coordinate the domain
    infrastructure/                            adapters: memory, SQLite, CSV files, the registry file, Ollama
    __main__.py                                interface: the command line

The design is in architecture/architecture.md and architecture/domain_model.md.
"""
