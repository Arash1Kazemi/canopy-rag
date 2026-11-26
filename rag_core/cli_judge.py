"""The judge command of `python -m rag_core` (Phase 10, proposal 16). __main__.py adds it with add_judge_commands.

    python -m rag_core judge --text FILE --layer N [--runs 2] [--source FILE] [--request "..."] [--prompt P14]
                             [--llm phi4-mini] [--db FILE] [--hierarchy-db FILE] [--run-id ID]

It judges the text in FILE as an output that goes to layer N (the layer that receives it). The threshold is the minimum judge
score of layer N in the layer registry (18 out of 20 for layers 0 to 2). The judge runs `--runs` times on the same prompt
(default 2, for the repeatability check of M20); every repeat is stored in the database (default data/project.sqlite) with the
run id, the prompt, the rubric, the model tag, the raw reply, the parsed scores and the outcome.

`--source` is the source knowledge the judge may rely on, `--request` is what the output was asked to do. Without them the prompt
says "(not given)", and the judge cannot check faithfulness well.

The real model runs through Ollama on 127.0.0.1:11500 (H06). Exit codes: 0 done (a pass, a fail and a failed judgment are all
results), 2 the setup cannot work (Ollama not reachable, the model not pulled, a layer that receives nothing or is not in the
registry, a missing or empty file, a run id that is already stored).
"""
import datetime as dt
import sys
from contextlib import closing
from pathlib import Path

from .cli_rag import DEFAULT_LLM_ID, SetupError, guarded, make_client, model_row, utc_now
from .infrastructure.project_db import database_path
from .infrastructure.sqlite_judging import SqliteJudgeRepository
from .judging.judge import DEFAULT_RUNS, JudgeService
from .judging.rubric import DEFAULT_RUBRIC
from .judging.threshold import threshold_policy_from_hierarchy
from .rag_wiring import load_hierarchy
from .workflows.judge_prompts import DEFAULT_JUDGE_PROMPT, load_judge_prompt

JUDGE_OPTIONS = {"num_predict": 512}      # the JSON reply with seven scores and an explanation is longer than an answer


def make_language_model(args):
    """The judge model through local Ollama. It checks first that the server answers and that the model is pulled."""
    from .infrastructure.ollama_language import OllamaLanguageModel
    row = model_row(args.llm)
    client = make_client()
    client.version()                                   # raises OllamaError when nothing listens on 127.0.0.1:11500
    if row["runtime_tag"] not in client.models():
        raise SetupError(f"not downloaded yet: {row['runtime_tag']}. Pull it while online (docs/operator_guide.md, Part 2).")
    return OllamaLanguageModel(row["runtime_tag"], client=client, options=dict(JUDGE_OPTIONS),
                               think=False if row["thinking_listed"] == "yes" else None)


def read_text(path, what):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise SetupError(f"cannot read the {what} file {path}: {error}") from error


def print_score(score):
    if not score.parse_ok:
        print(f"Repeat {score.repeat}: FAILED JUDGMENT, not a pass. The reply could not be read: {score.parse_error}")
        print(f"  raw reply: {score.raw_output[:300]!r}")
        return
    print(f"Repeat {score.repeat}: {score.outcome.upper()}  {score.total}/20 (threshold {score.threshold})")
    print("  " + ", ".join(f"{key} {points}" for key, points in score.scores))
    print(f"  explanation: {score.explanation}")
    for label, items in (("missing", score.missing_information), ("unsupported", score.unsupported_claims)):
        if items:
            print(f"  {label}: {'; '.join(items)}")
    if score.suggested_fix:
        print(f"  suggested fix: {score.suggested_fix}")


def cmd_judge(args):
    text = read_text(args.text, "text")
    source = read_text(args.source, "source") if args.source else ""
    hierarchy = load_hierarchy(args.hierarchy_db)
    policy = threshold_policy_from_hierarchy(hierarchy)
    policy.threshold_for(args.layer)                   # a layer that receives nothing is refused before any model is touched
    prompt = load_judge_prompt(args.prompt)
    run_id = args.run_id or "judge-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    model = make_language_model(args)
    db = Path(args.db) if args.db else database_path()
    with closing(SqliteJudgeRepository(db)) as repository:
        service = JudgeService(model, repository, DEFAULT_RUBRIC, prompt, policy, utc_now)
        result = service.judge(text, args.layer, run_id=run_id, runs=args.runs, source=source, request=args.request or "",
                               source_ref=Path(args.source).name if args.source else "")
    layer = hierarchy.layer_definition(args.layer)
    first = result.scores[0]
    print(f"Judge run {result.run_id}: prompt {first.prompt_id} (version {first.prompt_version}), rubric {first.rubric_id} "
          f"(version {first.rubric_version}), model {first.model_tag}")
    print(f"Target layer {args.layer} ({layer.name if layer else 'no name'}): needs {policy.detail_level_for(args.layer)}, "
          f"threshold {first.threshold} out of 20\n")
    for score in result.scores:
        print_score(score)
    if result.repeatability is not None:
        r = result.repeatability
        print(f"\nRepeatability (M20): same decision: {'yes' if r.same_decision else 'no'}, "
              f"same total: {'yes' if r.same_total else 'no'}" + (", a failed judgment among the runs" if r.any_invalid else ""))
    print(f"\nstored: {len(result.scores)} judgment(s) as run {result.run_id} in {db}")
    return 0


def add_judge_commands(sub):
    p = sub.add_parser("judge", help="judge a text with the rubric and the threshold of the layer that receives it (Phase 10)")
    p.add_argument("--text", required=True, help="the file with the text to judge (UTF-8)")
    p.add_argument("--layer", required=True, type=int, help="the layer that receives the text; its minimum judge score is the threshold")
    p.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="how many times to run the judge on the same prompt (default 2)")
    p.add_argument("--source", help="a file with the source knowledge the judge may rely on")
    p.add_argument("--request", help="what the text was asked to do")
    p.add_argument("--prompt", default=DEFAULT_JUDGE_PROMPT, help="judge prompt id from prompts/prompt_registry.csv (default P14)")
    p.add_argument("--llm", default=DEFAULT_LLM_ID, help="language model id (default phi4-mini)")
    p.add_argument("--db", help="the database file for the stored judgments (default data/project.sqlite or RAG_DATA_DB)")
    p.add_argument("--hierarchy-db", help="read the layer registry from this database instead of registry/layer_registry.csv")
    p.add_argument("--run-id", help="name of this judge run (default judge-<date and time>)")
    p.set_defaults(run=guarded(cmd_judge))
