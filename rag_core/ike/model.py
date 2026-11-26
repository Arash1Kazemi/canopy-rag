"""The Issue-Knowledge-Executor model (proposal section 13): typed relations between issues, knowledge and executors.

The model is an edge list. Each IkeRelation has a relation type (exactly the twelve of proposal 13.1), a source and a
target (each an EntityRef: a kind and a key), the node the relation belongs to, an optional evidence id (the document
or chunk that shows the relation) and the date it was recorded (from an injected clock).

The twelve relation types of proposal 13.1, in the proposal's order, with the Persian wording for traceability:

  1  issue_related_to_knowledge                  the issue is related to knowledge          مسئله با دانش مرتبط است
  2  issue_depends_on_knowledge                  the issue depends on knowledge             مسئله به دانش وابسته است
  3  issue_lacks_knowledge                       the issue lacks knowledge                  مسئله دچار کمبود دانش است
  4  issue_similar_to_issue                      the issue is similar to another issue      مسئله با مسئله دیگر مشابه است
  5  issue_decomposes_into_issue                 the issue decomposes into smaller issues   مسئله به مسئله‌های کوچک‌تر تجزیه می‌شود
  6  issue_blocked_by_issue                      the issue is blocked by another issue      مسئله توسط مسئله دیگر مسدود شده است
  7  executor_has_expertise                      the executor has expertise in an area      مجری در حوزه‌ای تخصص دارد
  8  executor_worked_on_project                  the executor has worked on a project       مجری قبلا روی پروژه‌ای کار کرده است
  9  executor_related_to_knowledge               the executor is related to a knowledge item مجری با قلم دانش مرتبط است
  10 executor_can_follow_issue                   the executor can follow up an issue        مجری می‌تواند مسئله‌ای را پیگیری کند
  11 knowledge_supports_answer                   the knowledge item supports an answer      قلم دانش از پاسخ پشتیبانی می‌کند
  12 knowledge_limits_or_conflicts_with_answer   the knowledge item limits or conflicts     قلم دانش پاسخ را محدود یا با آن
                                                 with an answer                             تعارض ایجاد می‌کند

Each sentence of 13.1 names its two sides, so each type allows exactly one source kind and one target kind (RULES).
Where the proposal names no entity, we chose (decisions to confirm):
- "an area" of expertise (7) is an `expertise` label, such as "route planning" (the expertise column of people.csv);
- the knowledge an issue lacks (3) is a `missing_knowledge` label (proposal 12.4 lists "missing knowledge");
- "an answer" (11, 12) is the answer or probable solution of one issue (proposal 12.5), so its key is that issue's id;
- a project (8) is referred to by an id; the project records come in Phase 12.
An executor is referred to by its id only: the Executor aggregate lives in its own package and is not imported here.
"""
import re
from dataclasses import dataclass
from enum import Enum

from ..issues.model import ISSUE_ID_PATTERN
from ..organization.model import NodeIdentifier
from ..shared.kernel import DomainError, parse_enum


class RelationType(str, Enum):
    ISSUE_RELATED_TO_KNOWLEDGE = "issue_related_to_knowledge"
    ISSUE_DEPENDS_ON_KNOWLEDGE = "issue_depends_on_knowledge"
    ISSUE_LACKS_KNOWLEDGE = "issue_lacks_knowledge"
    ISSUE_SIMILAR_TO_ISSUE = "issue_similar_to_issue"
    ISSUE_DECOMPOSES_INTO_ISSUE = "issue_decomposes_into_issue"
    ISSUE_BLOCKED_BY_ISSUE = "issue_blocked_by_issue"
    EXECUTOR_HAS_EXPERTISE = "executor_has_expertise"
    EXECUTOR_WORKED_ON_PROJECT = "executor_worked_on_project"
    EXECUTOR_RELATED_TO_KNOWLEDGE = "executor_related_to_knowledge"
    EXECUTOR_CAN_FOLLOW_ISSUE = "executor_can_follow_issue"
    KNOWLEDGE_SUPPORTS_ANSWER = "knowledge_supports_answer"
    KNOWLEDGE_LIMITS_OR_CONFLICTS_WITH_ANSWER = "knowledge_limits_or_conflicts_with_answer"

    @property
    def order(self):
        """1 to 12, the order of proposal 13.1. Used to sort edges and counts the same way on every run."""
        return list(RelationType).index(self) + 1

    @property
    def phrase(self):
        """A short readable phrase for summaries, such as 'decomposes into'."""
        return PHRASES[self]


PHRASES = {
    RelationType.ISSUE_RELATED_TO_KNOWLEDGE: "is related to",
    RelationType.ISSUE_DEPENDS_ON_KNOWLEDGE: "depends on",
    RelationType.ISSUE_LACKS_KNOWLEDGE: "lacks knowledge about",
    RelationType.ISSUE_SIMILAR_TO_ISSUE: "is similar to",
    RelationType.ISSUE_DECOMPOSES_INTO_ISSUE: "decomposes into",
    RelationType.ISSUE_BLOCKED_BY_ISSUE: "is blocked by",
    RelationType.EXECUTOR_HAS_EXPERTISE: "has expertise in",
    RelationType.EXECUTOR_WORKED_ON_PROJECT: "has worked on",
    RelationType.EXECUTOR_RELATED_TO_KNOWLEDGE: "is related to",
    RelationType.EXECUTOR_CAN_FOLLOW_ISSUE: "can follow up",
    RelationType.KNOWLEDGE_SUPPORTS_ANSWER: "supports the answer to",
    RelationType.KNOWLEDGE_LIMITS_OR_CONFLICTS_WITH_ANSWER: "limits or conflicts with the answer to",
}


class RefKind(str, Enum):
    """What a side of a relation is. The first five are things with ids; the last two are short labels."""
    ISSUE = "issue"
    KNOWLEDGE_ITEM = "knowledge_item"
    EXECUTOR = "executor"
    PROJECT = "project"
    ANSWER = "answer"                       # the answer or probable solution of one issue; the key is the issue id
    EXPERTISE = "expertise"                 # a label, such as "route planning"
    MISSING_KNOWLEDGE = "missing_knowledge"  # a label naming the knowledge an issue lacks

    @property
    def is_label(self):
        return self in (RefKind.EXPERTISE, RefKind.MISSING_KNOWLEDGE)

    @property
    def order(self):
        return list(RefKind).index(self) + 1


# relation type -> (the one allowed source kind, the one allowed target kind), read from the sentences of 13.1
RULES = {
    RelationType.ISSUE_RELATED_TO_KNOWLEDGE: (RefKind.ISSUE, RefKind.KNOWLEDGE_ITEM),
    RelationType.ISSUE_DEPENDS_ON_KNOWLEDGE: (RefKind.ISSUE, RefKind.KNOWLEDGE_ITEM),
    RelationType.ISSUE_LACKS_KNOWLEDGE: (RefKind.ISSUE, RefKind.MISSING_KNOWLEDGE),
    RelationType.ISSUE_SIMILAR_TO_ISSUE: (RefKind.ISSUE, RefKind.ISSUE),
    RelationType.ISSUE_DECOMPOSES_INTO_ISSUE: (RefKind.ISSUE, RefKind.ISSUE),
    RelationType.ISSUE_BLOCKED_BY_ISSUE: (RefKind.ISSUE, RefKind.ISSUE),
    RelationType.EXECUTOR_HAS_EXPERTISE: (RefKind.EXECUTOR, RefKind.EXPERTISE),
    RelationType.EXECUTOR_WORKED_ON_PROJECT: (RefKind.EXECUTOR, RefKind.PROJECT),
    RelationType.EXECUTOR_RELATED_TO_KNOWLEDGE: (RefKind.EXECUTOR, RefKind.KNOWLEDGE_ITEM),
    RelationType.EXECUTOR_CAN_FOLLOW_ISSUE: (RefKind.EXECUTOR, RefKind.ISSUE),
    RelationType.KNOWLEDGE_SUPPORTS_ANSWER: (RefKind.KNOWLEDGE_ITEM, RefKind.ANSWER),
    RelationType.KNOWLEDGE_LIMITS_OR_CONFLICTS_WITH_ANSWER: (RefKind.KNOWLEDGE_ITEM, RefKind.ANSWER),
}
# "similar" has no direction: A similar to B is the same edge as B similar to A, so it is stored with the smaller key first
SYMMETRIC = frozenset({RelationType.ISSUE_SIMILAR_TO_ISSUE})
# these two have a direction that must never come back to where it started
ACYCLIC = frozenset({RelationType.ISSUE_DECOMPOSES_INTO_ISSUE, RelationType.ISSUE_BLOCKED_BY_ISSUE})

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:\-]*")   # ids of items, chunks, executors and projects
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}([T ][0-9:.]+Z?)?")


def parse_relation_type(value):
    return value if isinstance(value, RelationType) else parse_enum(RelationType, str(value).strip(), "a relation type")


def parse_ref_kind(value):
    return value if isinstance(value, RefKind) else parse_enum(RefKind, str(value).strip(), "a reference kind")


def normalize_label(text):
    """A label in one form: trimmed, inner spaces collapsed, lower case. 'Route  Planning ' becomes 'route planning'."""
    return " ".join(str(text).split()).lower()


def natural_key(text):
    """Sort 'I2' before 'I10': digits compare as numbers."""
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", text) if p != "")


@dataclass(frozen=True)
class EntityRef:
    """One side of a relation: a kind and a key. An issue or an answer has an issue id as key (I01); a label kind has
    the normalized label; every other kind has an id without spaces (D11, P03, D11:3)."""
    kind: RefKind
    key: str

    def __post_init__(self):
        kind = parse_ref_kind(self.kind)
        object.__setattr__(self, "kind", kind)
        if kind.is_label:
            key = normalize_label(self.key or "")
            if not key:
                raise DomainError(f"a {kind.value} label must not be empty")
        else:
            key = str(self.key or "").strip()
            pattern = ISSUE_ID_PATTERN if kind in (RefKind.ISSUE, RefKind.ANSWER) else ID_PATTERN
            if not pattern.fullmatch(key):
                raise DomainError(f"{key!r} is not a valid {kind.value} id")
        object.__setattr__(self, "key", key)

    @property
    def sort_key(self):
        return (self.kind.order, natural_key(self.key))

    def __str__(self):
        return f"{self.kind.value}:{self.key}"


def ref(kind, key):
    return EntityRef(parse_ref_kind(kind), key)


@dataclass(frozen=True, kw_only=True)
class IkeRelation:
    """One typed edge of the IKE model. Equal edges have the same type, source and target (see `edge_key`)."""
    relation_type: RelationType
    source: EntityRef
    target: EntityRef
    node_id: NodeIdentifier
    created_at: str
    evidence: str = ""        # the document or chunk id that shows the relation; empty when the basis is a record
    basis: str = ""           # a short note on where the relation comes from, such as "people.csv expertise"

    def __post_init__(self):
        set_ = lambda name, value: object.__setattr__(self, name, value)
        kind = parse_relation_type(self.relation_type)
        set_("relation_type", kind)
        if not isinstance(self.node_id, NodeIdentifier):
            set_("node_id", NodeIdentifier(str(self.node_id)))
        for side in ("source", "target"):
            if not isinstance(getattr(self, side), EntityRef):
                raise DomainError(f"the {side} of a relation must be an EntityRef")
        want_source, want_target = RULES[kind]
        if self.source.kind != want_source or self.target.kind != want_target:
            raise DomainError(f"{kind.value} goes from a {want_source.value} to a {want_target.value}, "
                              f"not from a {self.source.kind.value} to a {self.target.kind.value}")
        if want_source == want_target and self.source.key == self.target.key:
            raise DomainError(f"{kind.value}: an issue cannot be related to itself ({self.source.key})")
        if kind in SYMMETRIC and self.target.sort_key < self.source.sort_key:
            source, target = self.source, self.target
            set_("source", target)
            set_("target", source)
        if not isinstance(self.created_at, str) or not DATE_PATTERN.fullmatch(self.created_at):
            raise DomainError(f"created_at must be an ISO date, not {self.created_at!r}")
        evidence = str(self.evidence or "").strip()
        if evidence and not ID_PATTERN.fullmatch(evidence):
            raise DomainError(f"evidence must be a document or chunk id, not {self.evidence!r}")
        set_("evidence", evidence)
        set_("basis", " ".join(str(self.basis or "").split()))

    @property
    def edge_key(self):
        """What makes two edges the same: type, source and target. The node, date, evidence and basis do not count."""
        return (self.relation_type, self.source, self.target)

    @property
    def sort_key(self):
        """Edges are listed by node, then the 13.1 order of the type, then source and target (ids in number order)."""
        return (natural_key(str(self.node_id)), self.relation_type.order, self.source.sort_key, self.target.sort_key)


def sorted_relations(relations):
    return sorted(relations, key=lambda r: r.sort_key)
