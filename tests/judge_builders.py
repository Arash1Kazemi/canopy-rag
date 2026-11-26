"""Small builders for the judge tests (Phase 10): a judge reply as the model would write it."""
import json

FULL = {"faithfulness": 5, "completeness": 4, "detail_fit": 3, "uncertainty": 3, "clarity": 2, "citability": 2,
        "no_unsupported_claims": 1}


def scores_with_total(total):
    """A valid set of criterion scores that adds up to `total` (0 to 20): points are taken away from the last criteria first."""
    left = 20 - total
    result = dict(FULL)
    for key in reversed(list(FULL)):
        cut = min(left, result[key])
        result[key] -= cut
        left -= cut
    assert sum(result.values()) == total
    return result


def reply(points=20, scores=None, **changes):
    """A judge reply (JSON text). `changes` set a top-level field; a field set to None is left out."""
    scores = scores_with_total(points) if scores is None else scores
    values = scores.values() if isinstance(scores, dict) else []
    body = {"scores": scores, "total": sum(v for v in values if isinstance(v, (int, float))),
            "explanation": "The output follows the source."}
    body.update(changes)
    return json.dumps({k: v for k, v in body.items() if v is not None})
