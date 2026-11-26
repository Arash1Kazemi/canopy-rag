"""The Executor entity (proposal sections 13.1 and 13.2, glossary "Executor").

An executor is a person, a team, a unit or an organizational capability that can help solve an issue (the proposal says
it is not only people). It lives in one node. An Executor is frozen: a change makes a new one through a method.

The profile holds what proposal 13.2 lists for the executor analysis: the organizational role, the known expertise (as
tags), the earlier projects, the documents written or owned, and availability when it is given. Everything but the id,
name, node and kind may be empty: an empty field means "not recorded", never a guess.
"""
import re
from dataclasses import dataclass, replace

from ..organization.model import NodeIdentifier
from ..shared.kernel import DomainError

EXECUTOR_ID_PATTERN = re.compile(r"[A-Z]+\d+")
# The glossary says "person, team, unit, or organizational capability"; people.csv gives persons only.
EXECUTOR_KINDS = ("person", "team", "unit", "capability")
# Availability is optional metadata (13.2). "" means it was not given.
AVAILABILITY = ("", "available", "limited", "unavailable")


@dataclass(frozen=True)
class ExecutorIdentifier:
    """The stable identifier of an executor, such as P01 (a person) or C01 (a capability)."""
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or not EXECUTOR_ID_PATTERN.fullmatch(self.value):
            raise DomainError(f"an executor id is capital letters followed by digits, such as P01, not {self.value!r}")

    @property
    def sort_key(self):
        letters = self.value.rstrip("0123456789")
        return (letters, int(self.value[len(letters):]))

    def __str__(self):
        return self.value


def as_executor_id(value):
    return value if isinstance(value, ExecutorIdentifier) else ExecutorIdentifier(str(value).strip())


def normalise_tag(text):
    """An expertise tag in one form: lowercase, one space between words, no edge spaces."""
    return " ".join(str(text).lower().split())


def stem(word):
    """A very light plural rule so that 'routes' matches 'route' and 'buses' matches 'bus'. It is applied to both sides of
    every comparison, so a wrong stem (such as 'analysi') is harmless: the same word gives the same stem."""
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


@dataclass(frozen=True)
class WrittenDocument:
    """A document an executor wrote or owns: its id (such as D15) and its title, which the matching reads."""
    doc_id: str
    title: str

    def __post_init__(self):
        if not isinstance(self.doc_id, str) or not self.doc_id.strip() or not isinstance(self.title, str):
            raise DomainError(f"a written document needs an id and a title, not {self.doc_id!r}, {self.title!r}")


@dataclass(frozen=True, kw_only=True)
class Executor:
    executor_id: ExecutorIdentifier
    name: str
    node_id: NodeIdentifier
    kind: str = "person"
    role: str = ""
    expertise: tuple = ()
    past_projects: tuple = ()
    documents_written: tuple = ()
    availability: str = ""

    def __post_init__(self):
        set_ = lambda name, value: object.__setattr__(self, name, value)
        set_("executor_id", as_executor_id(self.executor_id))
        if not isinstance(self.node_id, NodeIdentifier):
            set_("node_id", NodeIdentifier(str(self.node_id)))
        if not isinstance(self.name, str) or not self.name.strip():
            raise DomainError(f"executor {self.executor_id} needs a non-empty name")
        set_("name", self.name.strip())
        if self.kind not in EXECUTOR_KINDS:
            raise DomainError(f"executor {self.executor_id}: kind must be one of {', '.join(EXECUTOR_KINDS)}, not {self.kind!r}")
        set_("role", str(self.role).strip())
        if isinstance(self.expertise, str):
            raise DomainError(f"executor {self.executor_id}: expertise is a list of tags, not one text")
        set_("expertise", tuple(sorted({t for t in (normalise_tag(x) for x in self.expertise) if t})))
        set_("past_projects", tuple(str(p).strip() for p in self.past_projects if str(p).strip()))
        docs = [d if isinstance(d, WrittenDocument) else WrittenDocument(*d) for d in self.documents_written]
        set_("documents_written", tuple(sorted(set(docs), key=lambda d: d.doc_id)))
        if self.availability not in AVAILABILITY:
            raise DomainError(f"executor {self.executor_id}: availability is empty or one of "
                              f"{', '.join(a for a in AVAILABILITY if a)}, not {self.availability!r}")

    def with_changes(self, **changes):
        """A copy with other facts. The id never changes."""
        if "executor_id" in changes:
            raise DomainError("the id of an executor never changes")
        return replace(self, **changes)
