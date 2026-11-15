"""Shared kernel: values that the Organizational Hierarchy, Knowledge Management and Knowledge Transfer contexts all use.

Keep this file small. A word moves here only when two contexts must mean exactly the same thing by it.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DomainError(Exception):
    """A domain rule was broken. The message names the rule, for example 'H03: ...'."""


class Confidentiality(str, Enum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class TransferDetailLevel(str, Enum):
    """How detailed a transfer package is. Owned by Knowledge Transfer; a node's reporting format uses it."""
    EXECUTIVE = "executive"
    MANAGERIAL = "managerial"
    TECHNICAL_SUMMARY = "technical_summary"
    DETAILED_TECHNICAL = "detailed_technical"

    @property
    def rank(self):
        """1 is the least detailed. Detail gets coarser going up the hierarchy."""
        return list(TransferDetailLevel).index(self) + 1


def parse_enum(enum_type, value, what):
    try:
        return enum_type(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_type)
        raise DomainError(f"{what} must be one of {allowed}, not {value!r}") from None


CITATION_LEVELS = ("short", "long")   # short: [stem]; long: adds pages, headings and the chunk id (architecture/citation_model.md)


@dataclass(frozen=True)
class TransferRule:
    """What a layer needs from the nodes below it (proposal sections 6.3 and 10.1). The layer registry holds one per layer.

    Only the detail level is required. Every other field may be empty until the supervisor decides it: an empty field
    means "not decided", never a default number. Owned by Knowledge Transfer; the Organizational Hierarchy stores it.
    """
    detail_level: TransferDetailLevel
    min_judge_score: Optional[int] = None
    required_topics: tuple = ()
    excluded_topics: tuple = ()
    required_fields: tuple = ()
    output_format: str = ""
    max_words: Optional[int] = None
    citation_level: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.detail_level, TransferDetailLevel):
            raise DomainError(f"a transfer rule needs a detail level, not {self.detail_level!r}")
        if self.min_judge_score is not None and not (isinstance(self.min_judge_score, int) and 1 <= self.min_judge_score <= 20):
            raise DomainError(f"min_judge_score is a whole number from 1 to 20, not {self.min_judge_score!r}")
        if self.max_words is not None and not (isinstance(self.max_words, int) and self.max_words >= 1):
            raise DomainError(f"max_words is a whole number from 1, not {self.max_words!r}")
        if self.citation_level is not None and self.citation_level not in CITATION_LEVELS:
            raise DomainError(f"citation_level must be one of {', '.join(CITATION_LEVELS)}, not {self.citation_level!r}")
        for name in ("required_topics", "excluded_topics", "required_fields"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise DomainError(f"{name} is a tuple of non-empty texts")
            if len(set(values)) != len(values):
                raise DomainError(f"{name} lists the same entry twice")
        both = set(self.required_topics) & set(self.excluded_topics)
        if both:
            raise DomainError(f"a topic cannot be both required and excluded: {sorted(both)}")


@dataclass(frozen=True)
class DomainEvent:
    """Something important happened inside an aggregate. Aggregates collect events; the application layer reads them."""
    name: str
    details: tuple = field(default=())  # (key, value) pairs, so the event stays immutable
