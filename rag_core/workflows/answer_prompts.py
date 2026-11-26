"""Load an answer prompt from prompts/ by its registry id (P01 = version 1, P13 = version 2).

The domain takes the prompt text as an argument and reads no file; this small application-layer function reads the
registry and the template and hands the domain an AnswerPrompt. The same convention as the Phase 2 runner: a template
file ends with a newline, the prompt does not.
"""
import csv
from pathlib import Path

from ..rag.answering import AnswerPrompt
from ..shared.kernel import DomainError

PROMPTS_FOLDER = Path(__file__).resolve().parents[2] / "prompts"
DEFAULT_ANSWER_PROMPT = "P01"   # the Phase 2 prompt, so results stay comparable; P13 adds the conflict rule


def load_answer_prompt(prompt_id=DEFAULT_ANSWER_PROMPT, folder=None):
    folder = Path(folder) if folder is not None else PROMPTS_FOLDER
    with open(folder / "prompt_registry.csv", encoding="utf-8", newline="") as handle:
        rows = {row["prompt_id"]: row for row in csv.DictReader(handle)}
    row = rows.get(prompt_id)
    if row is None:
        raise DomainError(f"no prompt {prompt_id} in the prompt registry")
    if row["task"] != "answer":
        raise DomainError(f"prompt {prompt_id} is for {row['task']}, not for answering")
    text = (folder / row["file"]).read_text(encoding="utf-8")
    return AnswerPrompt(prompt_id, int(row["version"]), text[:-1] if text.endswith("\n") else text)
