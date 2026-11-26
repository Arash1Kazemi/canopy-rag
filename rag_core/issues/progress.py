"""ProgressPercentage: how far an issue has come, by fixed rules (H07, proposal section 14.1, decision A31).

In words: the proposal lists seven things that show progress. Each one is a factor that is either done (counts fully)
or not done (counts zero). One factor, "sub-issues solved", can be partly done: it is the share of the sub-issues that
are solved. Each factor has a weight, and the weights add up to 100. The progress is the sum of weight times how much
of the factor is done, rounded down to a whole number. Only a solved issue shows 100; any other issue shows at most 99.

The weights come from a config file (config/issue_progress_weights.csv). They are untuned starting values.
The same issue and sub-issues always give the same number, in any order (H07): only counts are used, never order.
"""
from dataclasses import dataclass
from fractions import Fraction

from ..shared.kernel import DomainError
from .status import IssueStatus

# The seven factors of proposal section 14.1, in the proposal's order.
FACTORS = (
    "sub_issues_defined",       # sub-issues have been defined
    "supporting_knowledge",     # supporting knowledge is linked
    "executor_mapped",          # an executor is mapped
    "solution_proposed",        # an answer or a solution is proposed
    "research_completed",       # the required research is complete
    "sub_issues_solved",        # the dependent sub-issues are solved (a share)
    "review_approved",          # the approval or review is done
)


@dataclass(frozen=True)
class ProgressPercentage:
    """A whole number from 0 to 100."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or isinstance(self.value, bool) or not 0 <= self.value <= 100:
            raise DomainError(f"a progress percentage is a whole number from 0 to 100, not {self.value!r}")

    def __str__(self):
        return f"{self.value}%"


@dataclass(frozen=True)
class ProgressWeights:
    """One whole-number weight per factor; the weights add up to 100."""
    weights: tuple       # (factor, weight) pairs

    def __post_init__(self):
        pairs = tuple(dict(self.weights).items())
        object.__setattr__(self, "weights", tuple(sorted(pairs, key=lambda p: FACTORS.index(p[0]) if p[0] in FACTORS else -1)))
        names = [name for name, _ in self.weights]
        if sorted(names) != sorted(FACTORS):
            raise DomainError(f"progress weights need exactly the factors {', '.join(FACTORS)}; got {', '.join(names)}")
        for name, weight in self.weights:
            if not isinstance(weight, int) or isinstance(weight, bool) or weight < 0:
                raise DomainError(f"the weight of {name} is a whole number from 0, not {weight!r}")
        if sum(w for _, w in self.weights) != 100:
            raise DomainError(f"progress weights add up to 100, not {sum(w for _, w in self.weights)}")

    @classmethod
    def of(cls, mapping):
        return cls(tuple(mapping.items()))

    def weight(self, factor):
        return dict(self.weights)[factor]


def progress_factors(issue, sub_issues):
    """How much of each factor is done, from 0 to 1 (as exact fractions). `sub_issues` are the issue's direct children."""
    children = [s for s in sub_issues if s.parent_issue_id == issue.issue_id]
    solved = sum(1 for s in children if s.status == IssueStatus.SOLVED)
    done = lambda flag: Fraction(1 if flag else 0)
    return {
        "sub_issues_defined": done(children),
        "supporting_knowledge": done(issue.knowledge_ids),
        "executor_mapped": done(issue.executor_ids),
        "solution_proposed": done(issue.proposed_solution.strip()),
        "research_completed": done(issue.research_completed),
        "sub_issues_solved": Fraction(solved, len(children)) if children else Fraction(0),
        "review_approved": done(issue.review_approved),
    }


def compute_progress(issue, sub_issues, weights):
    """H07: the progress of an issue from fixed rules. The order of `sub_issues` never matters."""
    if issue.status == IssueStatus.SOLVED:
        return ProgressPercentage(100)
    factors = progress_factors(issue, sub_issues)
    total = sum(weights.weight(name) * share for name, share in factors.items())
    return ProgressPercentage(min(int(total), 99))     # int() of a positive Fraction rounds down
