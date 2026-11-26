"""Compare a draft issue with the issues already in its node (proposal 12.1 steps 3 and 4, decision A34).

In words: take the words of the draft (title and description) and of each existing issue, drop the stopwords
(little words such as "the" and "on" that every text has), and count the words the two share. The score is the shared
words divided by all the different words of the two together (the Jaccard score). 1 means the same words, 0 means no
word in common.

Only issues of the draft's own node are compared (12: "the existing issues of the same node"). An issue from another
node is never a candidate, whatever its words.

No threshold says "this is a duplicate". The result is a ranked list for a person to read. A threshold is chosen only
after labelled pairs of issues exist (the same lesson as M10 and M11 for documents).

The slot for Phase 8: pass `similarity`, a function (draft text, issue text) -> number from 0 to 1, for example a
cosine similarity of two embeddings. The candidates are then ranked by it; the shared words are still shown, because a
person needs a reason they can read.
"""
import re
from dataclasses import dataclass
from fractions import Fraction

from ..organization.model import NodeIdentifier
from ..shared.kernel import DomainError

# A short, fixed English list. Numbers are kept: "Route 7" and "Route 12" must stay different.
STOPWORDS = frozenset("""
a an the and or but if of on in at to for from by with without as into onto over under about after before
is are was were be been being has have had do does did not no nor so than that this these those there their
it its they them we our you your he she his her i me my
can could should would will may might must shall
all any each every some more most other such only own same very too also just
what which who whom whose when where why how
says say said
""".split())

WORD = re.compile(r"[a-z0-9]+")


def content_words(text):
    """The set of words of a text, lowercased, without stopwords."""
    return frozenset(w for w in WORD.findall(text.lower()) if w not in STOPWORDS)


@dataclass(frozen=True)
class IssueDraft:
    """A new issue that is not saved yet: what a person typed, in the node where it would live."""
    node_id: object
    title: str
    description: str = ""

    def __post_init__(self):
        if not isinstance(self.node_id, NodeIdentifier):
            object.__setattr__(self, "node_id", NodeIdentifier(str(self.node_id)))
        if not isinstance(self.title, str) or not self.title.strip():
            raise DomainError("a draft issue needs a non-empty title")

    @property
    def text(self):
        return f"{self.title} {self.description}"


@dataclass(frozen=True)
class IssueMatch:
    """One ranked candidate: an existing issue, its score, the word score and the shared words."""
    issue_id: object
    title: str
    score: float
    word_score: float
    shared_words: tuple


def word_overlap(left_words, right_words):
    """The Jaccard score of two word sets, as an exact fraction."""
    union = left_words | right_words
    return Fraction(len(left_words & right_words), len(union)) if union else Fraction(0)


def compare_draft(draft, issues, similarity=None):
    """Ranked IssueMatch candidates from the draft's node only. A candidate shares at least one word with the draft,
    or (with `similarity`) has a score above 0. Ties are broken by issue id, so the order is the same on every run."""
    draft_words = content_words(draft.text)
    matches = []
    for issue in issues:
        if issue.node_id != draft.node_id:
            continue                                         # 12: compare inside the node only (H01 for issues)
        issue_text = f"{issue.title} {issue.description}"
        words = content_words(issue_text)
        shared = draft_words & words
        word_score = round(float(word_overlap(draft_words, words)), 3)
        score = word_score if similarity is None else round(float(similarity(draft.text, issue_text)), 3)
        if shared or score > 0:
            matches.append(IssueMatch(issue.issue_id, issue.title, score, word_score, tuple(sorted(shared))))
    return sorted(matches, key=lambda m: (-m.score, -m.word_score, m.issue_id.number))
