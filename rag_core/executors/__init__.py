"""Executor Management (Phase 9, proposal sections 13.1 and 13.2): who can help with an issue.

The domain part (this package) imports only the standard library and other domain packages. Use cases are in
rag_core/workflows/executors.py; storage and the CSV import are in rag_core/infrastructure/.
"""
from .matching import FACTORS, MatchWeights, ScoreComponent, ExecutorMatch, rank_executors
from .model import AVAILABILITY, EXECUTOR_KINDS, Executor, ExecutorIdentifier, WrittenDocument, normalise_tag, stem
