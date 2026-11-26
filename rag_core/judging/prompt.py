"""The judge prompt (Phase 10): a versioned template with five blanks, filled in one pass.

The template file lives in prompts/ and is listed in prompt_registry.csv with task "judge" (P14). workflows/judge_prompts.py
loads it. The domain reads no file: it receives the text.

Filling is done in one pass over the template, so a blank-like text inside the output being judged (for example "{{source}}")
is copied as text and never filled again.
"""
import re
from dataclasses import dataclass

from ..shared.kernel import DomainError

BLANK = re.compile(r"\{\{(\w+)\}\}")
BLANKS = {"rubric", "detail_level", "request", "source", "candidate"}
NOT_GIVEN = "(not given)"


@dataclass(frozen=True)
class JudgePrompt:
    prompt_id: str
    version: int
    template: str

    def __post_init__(self):
        found = set(BLANK.findall(self.template))
        if found != BLANKS:
            raise DomainError(f"judge prompt {self.prompt_id} must have exactly the blanks {sorted(BLANKS)}, it has {sorted(found)}")

    def render(self, *, rubric, detail_level, request, source, candidate):
        values = {"rubric": rubric, "detail_level": detail_level, "request": request.strip() or NOT_GIVEN,
                  "source": source.strip() or NOT_GIVEN, "candidate": candidate}
        return BLANK.sub(lambda m: values[m.group(1)], self.template)
