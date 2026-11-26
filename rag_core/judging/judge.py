"""The judge use case (Phase 10, proposal 16): text in, stored scores out.

For one text and one target layer it:
1. looks up the threshold and the detail level of that layer (a layer that receives nothing is refused);
2. renders the judge prompt (rubric, detail level, request, source, the text to judge);
3. asks the language model `runs` times with the same prompt (two repeats give the repeatability check of M20);
4. reads each reply with the strict score parser, and decides pass, fail or invalid against the threshold;
5. stores all repeats under one run id, whole or not at all, and returns them with the repeatability.

The model only scores. It never decides pass or fail: the outcome comes from the stored threshold of the target layer. A reply
that cannot be read is a failed judgment (outcome "invalid"), which is never a pass. A model that cannot be reached raises its
own error, nothing is stored, and the caller reports a setup problem: that is not a judgment.

The language model, the repository, the rubric, the prompt, the threshold policy and the clock are all arguments, so unit
tests pass a stub judge and no real model is ever needed.
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

from ..shared.kernel import DomainError
from .model import FAIL, INVALID, PASS, JudgeScore, Repeatability, repeatability_of
from .parser import parse_judge_reply

DEFAULT_RUNS = 2        # two runs on the same input are enough to see whether the judge repeats itself (M20)


@dataclass(frozen=True)
class JudgeRunResult:
    run_id: str
    scores: tuple
    repeatability: Optional[Repeatability]


class JudgeService:
    def __init__(self, model, repository, rubric, prompt, policy, clock):
        """`model` has `generate(prompt) -> text` (the LanguageModel port), `repository` is a JudgeScoreRepository,
        `policy` a ThresholdPolicy, `clock` returns the time as text. The tag stored with each score is `model.model_tag`."""
        self.model = model
        self.repository = repository
        self.rubric = rubric
        self.prompt = prompt
        self.policy = policy
        self.clock = clock

    def judge(self, text, target_layer, *, run_id, runs=DEFAULT_RUNS, source="", request="", source_ref=""):
        if not isinstance(text, str) or not text.strip():
            raise DomainError("there is nothing to judge: the text is empty")
        if not isinstance(run_id, str) or not run_id.strip():
            raise DomainError("a judge run needs a run id")
        if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
            raise DomainError(f"the number of runs is a whole number from 1, not {runs!r}")
        if self.repository.run(run_id):
            raise DomainError(f"run {run_id} is already stored; use another run id so no judgment is overwritten")
        threshold = self.policy.threshold_for(target_layer)
        prompt = self.prompt.render(rubric=self.rubric.as_prompt_text(), detail_level=self.policy.detail_level_for(target_layer),
                                    request=request, source=source, candidate=text)
        tag = getattr(self.model, "model_tag", "unknown")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        scores = []
        for repeat in range(1, runs + 1):
            raw = self.model.generate(prompt)
            scores.append(self._score(run_id, repeat, tag, target_layer, threshold, digest, source_ref, raw))
        self.repository.add_run(scores)
        return JudgeRunResult(run_id, tuple(scores), repeatability_of(scores) if runs >= 2 else None)

    def _score(self, run_id, repeat, tag, target_layer, threshold, digest, source_ref, raw):
        parsed = parse_judge_reply(raw, self.rubric)
        common = dict(run_id=run_id, repeat=repeat, prompt_id=self.prompt.prompt_id, prompt_version=self.prompt.version,
                      rubric_id=self.rubric.rubric_id, rubric_version=self.rubric.version, model_tag=tag,
                      target_layer=target_layer, threshold=threshold.min_score, text_sha256=digest, source_ref=source_ref,
                      raw_output=raw if isinstance(raw, str) else repr(raw), judged_at=self.clock())
        if not parsed.ok:
            return JudgeScore(**common, parse_ok=False, parse_error=parsed.error, scores=(), total=None, explanation="",
                              missing_information=(), unsupported_claims=(), suggested_fix="", outcome=INVALID)
        p = parsed.parsed
        return JudgeScore(**common, parse_ok=True, parse_error="", scores=p.scores, total=p.total, explanation=p.explanation,
                          missing_information=p.missing_information, unsupported_claims=p.unsupported_claims,
                          suggested_fix=p.suggested_fix, outcome=PASS if threshold.passes(p.total) else FAIL)
