"""Issue Management (Phase 7): issues and sub-issues, statuses, progress, comparison, relative position, suggestions.

The domain part (this package) imports only the standard library and other domain packages. Use cases are in
rag_core/workflows/issues.py; storage is in rag_core/infrastructure/.
"""
from .comparison import IssueDraft, IssueMatch, compare_draft, content_words
from .model import ISSUE_TYPES, PRIORITIES, Issue, IssueIdentifier
from .progress import FACTORS, ProgressPercentage, ProgressWeights, compute_progress, progress_factors
from .rules import RelativePosition, check_issues, relative_position, sibling_order
from .status import ALLOWED_MOVES, IssueStatus, parse_status
from .suggestions import SubIssueSuggestion, fill_prompt, parse_suggestions
