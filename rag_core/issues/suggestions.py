"""Sub-issue suggestions (proposal 12.1 step 7 and 12.2): what the language model proposes, before a person decides.

A suggestion is only text. It becomes a sub-issue only when a person accepts it (as it is or edited); a rejected one is
simply left out (decision A35). The model's reply is parsed here, in plain Python, so a strange reply can never
create an issue by itself.
"""
import re
from dataclasses import dataclass

from ..shared.kernel import DomainError

BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class SubIssueSuggestion:
    title: str
    description: str

    def __post_init__(self):
        for name in ("title", "description"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise DomainError(f"a sub-issue suggestion needs a non-empty {name}")
            object.__setattr__(self, name, " ".join(value.split()))

    def edited(self, title=None, description=None):
        """The suggestion as a person changed it."""
        return SubIssueSuggestion(title or self.title, description or self.description)


def parse_suggestions(reply):
    """Read the model's reply: one suggestion per line, `title | description` (the format prompt P12 asks for).

    Lines without a bar use the first colon instead; a line with neither is a title, and the title is then also the
    description. Bullets and numbers at the start are removed, empty lines and lines ending in ':' skipped, and a
    repeated title kept once.
    """
    suggestions, seen = [], set()
    for line in (reply or "").splitlines():
        line = BULLET.sub("", line).strip().strip("*").strip()
        if not line or line.endswith(":"):       # an empty line, or an intro such as "Here are some ideas:"
            continue
        if "|" in line:
            title, _, description = line.partition("|")
        elif ": " in line:
            title, _, description = line.partition(": ")
        else:
            title, description = line, line
        title, description = title.strip().strip("*").strip(), description.strip() or title.strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        suggestions.append(SubIssueSuggestion(title, description))
    return suggestions


def fill_prompt(template, **values):
    """Put the values into a versioned prompt's {{blanks}}. Every blank must get a value, and every value a blank."""
    blanks = set(PLACEHOLDER.findall(template))
    if blanks != set(values):
        raise DomainError(f"the prompt's blanks {sorted(blanks)} differ from the values given {sorted(values)}")
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)
