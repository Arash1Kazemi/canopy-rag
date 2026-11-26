"""The strict score parser (Phase 10, proposal 16.2).

The judge must reply with one JSON object and nothing else:

    {"scores": {<criterion key>: <whole number>, ...}, "total": <whole number>, "explanation": "<text>",
     "missing_information": [<text>], "unsupported_claims": [<text>], "suggested_fix": "<text>"}

The last three are optional. The parser accepts exactly this and refuses everything else (decision A70): no code fence, no
text around the object, no repaired number, no float, no text for a number, no missing or extra criterion, no score above its
maximum or below 0, no total that differs from the sum, no total outside 0 to 20, no field it does not know (so a "verdict" or
"passed" written by the model is refused: the system decides pass or fail). Any failure is a failed judgment, which is never a
pass. `parse_judge_reply` never raises.
"""
import json
from dataclasses import dataclass
from typing import Optional

from .rubric import RUBRIC_TOTAL

REQUIRED = ("scores", "total", "explanation")
LISTS = ("missing_information", "unsupported_claims")
OPTIONAL = LISTS + ("suggested_fix",)


class _Refused(ValueError):
    """Raised inside the parser only; the public function turns it into a ParseResult."""


@dataclass(frozen=True)
class ParsedScore:
    """What a valid reply says. `scores` are (criterion key, points) pairs in the order of the rubric."""
    scores: tuple
    total: int
    explanation: str
    missing_information: tuple = ()
    unsupported_claims: tuple = ()
    suggested_fix: str = ""


@dataclass(frozen=True)
class ParseResult:
    ok: bool
    parsed: Optional[ParsedScore] = None
    error: str = ""


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise _Refused("the JSON object repeats a key")
    return dict(pairs)


def _no_constants(name):
    raise _Refused(f"{name} is not a valid JSON number")


def _texts(body, name):
    if name not in body:
        return ()
    value = body[name]
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise _Refused(f"{name} must be a list of texts")
    return tuple(value)


def _read(raw, rubric):
    if not isinstance(raw, str):
        raise _Refused("the reply is not text")
    try:
        body = json.loads(raw.strip(), object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
    except (json.JSONDecodeError, RecursionError):
        raise _Refused("the reply is not valid JSON (it must be one JSON object and nothing else)") from None
    if not isinstance(body, dict):
        raise _Refused("the reply is JSON but not one object")
    unknown = sorted(set(body) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise _Refused(f"unknown field(s): {', '.join(unknown)}")
    missing = [name for name in REQUIRED if name not in body]
    if missing:
        raise _Refused(f"missing field(s): {', '.join(missing)}")

    scores = body["scores"]
    if not isinstance(scores, dict):
        raise _Refused("scores must be an object of criterion key and points")
    absent = [k for k in rubric.keys if k not in scores]
    if absent:
        raise _Refused(f"no score for criterion {', '.join(absent)}")
    extra = sorted(set(scores) - set(rubric.keys))
    if extra:
        raise _Refused(f"score for a criterion that is not in rubric {rubric.rubric_id}: {', '.join(extra)}")
    for criterion in rubric.criteria:
        value = scores[criterion.key]
        if not _whole(value):
            raise _Refused(f"the score of {criterion.key} must be a whole number, not {value!r}")
        if not 0 <= value <= criterion.points:
            raise _Refused(f"the score of {criterion.key} is {value}, but it must be from 0 to {criterion.points}")

    total = body["total"]
    if not _whole(total):
        raise _Refused(f"total must be a whole number, not {total!r}")
    if not 0 <= total <= RUBRIC_TOTAL:
        raise _Refused(f"total is {total}, but it must be from 0 to {RUBRIC_TOTAL}")
    summed = sum(scores[k] for k in rubric.keys)
    if total != summed:
        raise _Refused(f"total is {total}, but the criteria add up to {summed}")

    explanation = body["explanation"]
    if not isinstance(explanation, str) or not explanation.strip():
        raise _Refused("the explanation must be a text that is not empty")
    fix = body.get("suggested_fix", "")
    if not isinstance(fix, str):
        raise _Refused("suggested_fix must be a text")
    return ParsedScore(tuple((k, scores[k]) for k in rubric.keys), total, explanation.strip(),
                       _texts(body, "missing_information"), _texts(body, "unsupported_claims"), fix.strip())


def parse_judge_reply(raw, rubric):
    """The reply read against a rubric: ParseResult(ok=True, parsed=...) or ParseResult(ok=False, error=the reason)."""
    try:
        return ParseResult(True, _read(raw, rubric))
    except _Refused as refused:
        return ParseResult(False, None, str(refused))
