"""Load a judge prompt from prompts/ by its registry id (P14 = the rubric judge, version 1).

The domain takes the prompt text as an argument and reads no file; this small application-layer function reads the registry
and the template and hands the domain a JudgePrompt. Same convention as workflows/answer_prompts.py: a template file ends with
a newline, the prompt does not. P04, the Phase 2 reference judge, has other blanks and cannot be loaded here.
"""
import csv
from pathlib import Path

from ..judging.prompt import JudgePrompt
from ..shared.kernel import DomainError

PROMPTS_FOLDER = Path(__file__).resolve().parents[2] / "prompts"
DEFAULT_JUDGE_PROMPT = "P14"


def load_judge_prompt(prompt_id=DEFAULT_JUDGE_PROMPT, folder=None):
    folder = Path(folder) if folder is not None else PROMPTS_FOLDER
    with open(folder / "prompt_registry.csv", encoding="utf-8", newline="") as handle:
        rows = {row["prompt_id"]: row for row in csv.DictReader(handle)}
    row = rows.get(prompt_id)
    if row is None:
        raise DomainError(f"no prompt {prompt_id} in the prompt registry")
    if row["task"] != "judge":
        raise DomainError(f"prompt {prompt_id} is for {row['task']}, not for judging")
    text = (folder / row["file"]).read_text(encoding="utf-8")
    return JudgePrompt(prompt_id, int(row["version"]), text[:-1] if text.endswith("\n") else text)
