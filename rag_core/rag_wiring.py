"""Wiring for the case study (Phase 8D): the repositories, the hierarchy and the ingest-if-needed step that the commands
`index`, `ask` and `evaluate` and the Phase 2 runner's `--engine core` share.

This is a plain module on top of the layers (like cli_issues.py), not a layer: it may use the adapters. It reads the
registry and the case-study Markdown files straight from their folders, so it does not depend on a possibly stale copy
in data/project.sqlite.
"""
from pathlib import Path

from .infrastructure.registry_csv import CsvHierarchyRepository
from .infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from .ingestion.case_study import manifest_requests
from .ingestion.extractors import Extractors
from .ingestion.service import FAILED, IngestionService
from .knowledge.chunking import DEFAULT_POLICY
from .organization.directory import HierarchyNodeDirectory
from .rag.retrieval import Retriever

PROJECT = Path(__file__).resolve().parent.parent
CASE = PROJECT / "case_study"
REGISTRY = PROJECT / "registry" / "node_layer_registry.csv"
LAYER_REGISTRY = PROJECT / "registry" / "layer_registry.csv"


def load_hierarchy(hierarchy_db=None):
    """The hierarchy from a hierarchy database, or from the registry CSV files when none is given."""
    if hierarchy_db:
        repo = SqliteHierarchyRepository(hierarchy_db)
        try:
            return repo.load()
        finally:
            repo.close()
    return CsvHierarchyRepository(REGISTRY, LAYER_REGISTRY).load()


def ingest_case_study_if_needed(repository, hierarchy, policy=DEFAULT_POLICY, clock=None):
    """Ingest the case-study Markdown files into `repository` unless it already holds knowledge.

    Returns (ingested, results): `ingested` is False when the repository already had items and nothing was done."""
    if repository.all_items():
        return False, []
    extra = {} if clock is None else {"clock": clock}
    service = IngestionService(hierarchy, repository, Extractors(), policy=policy, **extra)
    results = [service.register(r) for r in manifest_requests(CASE)]
    failed = [r for r in results if r.outcome == FAILED]
    if failed:
        raise RuntimeError("ingestion failed for " + ", ".join(f"{r.request.item_id}: {r.detail}" for r in failed))
    return True, results


def make_retriever(index, embedder, hierarchy, repository):
    return Retriever(index, embedder, HierarchyNodeDirectory(hierarchy), repository)


def prepare_case_study(repository, index, embedder, hierarchy, *, policy=DEFAULT_POLICY, clock=None, lifecycle=None,
                       batch_size=None):
    """Ingest the case study if the repository is empty, then embed and index the active chunks.

    Returns (retriever, ingested, report): the Retriever on this index, whether ingestion ran, and the IndexingReport.
    Indexing is idempotent and rebuilds when the embedding model or the policy changed (rag/indexing.py)."""
    from .ingestion.service import utc_now
    from .rag.indexing import DEFAULT_BATCH_SIZE, index_chunks
    now = clock or utc_now
    ingested, _ = ingest_case_study_if_needed(repository, hierarchy, policy, clock=now)
    report = index_chunks(repository, index, embedder, chunking_policy=policy, clock=now, lifecycle=lifecycle,
                          batch_size=batch_size or DEFAULT_BATCH_SIZE)
    return make_retriever(index, embedder, hierarchy, repository), ingested, report
