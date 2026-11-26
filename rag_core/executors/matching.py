"""Match an issue to executors with a score a person can read (proposal 13.2).

In words: take the words of the issue (title, description, field of activity and category) without the stopwords, and
the words of each executor's expertise tags. A tag that shares a word with the issue is a matched tag. Four components
make the score, each a share from 0 to 1 times its weight:

- tags: the average, over the executor's tags, of how much of each tag's words the issue contains. "route planning"
  with only "route" in the issue covers half of the tag. An executor with no tags gets 0.
- documents: 1 when a document the executor wrote has a title that shares a word with the issue, else 0.
- same_node: 1 when the executor lives in the issue's node, else 0.
- availability: available 1, limited 0.5, unavailable or not given 0. Its weight is 0 for now.

The weights come from config/executor_match_weights.csv (untuned) and add up to 100, so the score is a number from 0 to
100. Every component is in the result with the words that made it, so nothing is hidden. The ranking is by score, and a
tie is broken by executor id. The same inputs give the same order on every run. Nothing here is a threshold: it is a
ranked list for a person to read.

A candidate needs a reason: a matched tag or a matching document. An executor with neither is left out unless the
caller asks for everyone.
"""
from dataclasses import dataclass
from fractions import Fraction

from ..issues.comparison import content_words
from ..shared.kernel import DomainError
from .model import stem

FACTORS = ("tags", "documents", "same_node", "availability")
AVAILABILITY_SHARE = {"available": Fraction(1), "limited": Fraction(1, 2), "unavailable": Fraction(0), "": Fraction(0)}


@dataclass(frozen=True)
class MatchWeights:
    """One whole-number weight per component; the weights add up to 100."""
    weights: tuple       # (factor, weight) pairs

    def __post_init__(self):
        pairs = tuple(dict(self.weights).items())
        object.__setattr__(self, "weights", tuple(sorted(pairs, key=lambda p: FACTORS.index(p[0]) if p[0] in FACTORS else -1)))
        names = [name for name, _ in self.weights]
        if sorted(names) != sorted(FACTORS):
            raise DomainError(f"match weights need exactly the factors {', '.join(FACTORS)}; got {', '.join(names)}")
        for name, weight in self.weights:
            if not isinstance(weight, int) or isinstance(weight, bool) or weight < 0:
                raise DomainError(f"the weight of {name} is a whole number from 0, not {weight!r}")
        if sum(w for _, w in self.weights) != 100:
            raise DomainError(f"match weights add up to 100, not {sum(w for _, w in self.weights)}")

    @classmethod
    def of(cls, mapping):
        return cls(tuple(mapping.items()))

    def weight(self, factor):
        return dict(self.weights)[factor]


@dataclass(frozen=True)
class ScoreComponent:
    """One part of a score: its name, weight, share (0 to 1), points (weight times share) and the evidence.
    detail is a tuple of readable lines, for example "route planning: route"."""
    name: str
    weight: int
    share: float
    points: float
    detail: tuple = ()


@dataclass(frozen=True)
class ExecutorMatch:
    """One ranked executor with the full explanation of the score."""
    executor_id: object
    name: str
    node_id: object
    role: str
    availability: str
    score: float
    components: tuple
    matched_tags: tuple          # (tag, shared words) pairs
    matched_documents: tuple     # (doc id, title, shared words) triples

    def component(self, name):
        return next(c for c in self.components if c.name == name)

    def explain(self):
        """The score and its parts as text lines."""
        lines = [f"{self.executor_id} {self.name} ({self.node_id}, {self.role or 'no role'}): {self.score:g} of 100"]
        for c in self.components:
            lines.append(f"  {c.name}: {c.points:g} (weight {c.weight}, share {c.share:g})")
            lines += [f"    {d}" for d in c.detail]
        return lines


def issue_words(issue):
    """The stemmed words of an issue's title, description, field of activity and category, without stopwords."""
    text = f"{issue.title} {issue.description} {issue.field_of_activity} {issue.category}"
    return frozenset(stem(w) for w in content_words(text))


def _words(text):
    return frozenset(stem(w) for w in content_words(text))


def rank_executors(issue, executors, weights, include_unmatched=False):
    """Ranked ExecutorMatch list for the executors given (the caller chooses which nodes they come from)."""
    words = issue_words(issue)
    matches = []
    for executor in executors:
        tag_hits, coverage = [], Fraction(0)
        for tag in executor.expertise:
            tag_words = _words(tag)
            shared = words & tag_words
            if shared:
                tag_hits.append((tag, tuple(sorted(shared))))
                coverage += Fraction(len(shared), len(tag_words))
        tag_share = coverage / len(executor.expertise) if executor.expertise else Fraction(0)
        doc_hits = []
        for doc in executor.documents_written:
            shared = words & _words(doc.title)
            if shared:
                doc_hits.append((doc.doc_id, doc.title, tuple(sorted(shared))))
        if not (tag_hits or doc_hits or include_unmatched):
            continue
        shares = {
            "tags": tag_share,
            "documents": Fraction(1 if doc_hits else 0),
            "same_node": Fraction(1 if executor.node_id == issue.node_id else 0),
            "availability": AVAILABILITY_SHARE[executor.availability],
        }
        details = {
            "tags": tuple(f"{tag}: {', '.join(shared)}" for tag, shared in tag_hits) or ("no tag matched",),
            "documents": tuple(f"{doc_id} {title}: {', '.join(shared)}" for doc_id, title, shared in doc_hits) or ("no document matched",),
            "same_node": (f"executor in {executor.node_id}, issue in {issue.node_id}",),
            "availability": (executor.availability or "not given",),
        }
        points = {name: weights.weight(name) * share for name, share in shares.items()}
        components = tuple(ScoreComponent(name, weights.weight(name), round(float(shares[name]), 3), round(float(points[name]), 3),
                                          details[name]) for name in FACTORS)
        matches.append((sum(points.values()), executor, ExecutorMatch(
            executor.executor_id, executor.name, executor.node_id, executor.role, executor.availability,
            round(float(sum(points.values())), 2), components, tuple(tag_hits), tuple(doc_hits))))
    # the exact score decides, then the executor id, so the order is the same on every run
    matches.sort(key=lambda m: (-m[0], m[1].executor_id.sort_key))
    return [m[2] for m in matches]
