"""Prompt templates live in files, are versioned, and are listed in prompt_registry.csv."""
import re
from pathlib import Path

from .config import PROMPTS
from .corpus import read_csv

BLANK = re.compile(r"\{\{(\w+)\}\}")


class PromptError(ValueError):
    pass


def render(template, **values):
    """Fill every {{blank}}. A missing value or an unused value is an error, never a silent gap."""
    blanks = set(BLANK.findall(template))
    if blanks != set(values):
        raise PromptError(f"blanks {sorted(blanks)} do not match values {sorted(values)}")
    return BLANK.sub(lambda m: str(values[m.group(1)]), template)


class Prompts:
    def __init__(self, folder=PROMPTS):
        self.folder = Path(folder)
        self.rows = {r["prompt_id"]: r for r in read_csv(self.folder / "prompt_registry.csv")}

    def template(self, prompt_id):
        text = (self.folder / self.rows[prompt_id]["file"]).read_text(encoding="utf-8")
        return text[:-1] if text.endswith("\n") else text  # a file ends with a newline, the prompt does not

    def render(self, prompt_id, **values):
        return render(self.template(prompt_id), **values)
