"""The Phase 8D evaluation: the 26 answer-key questions through the core, graded with the Phase 2 grading code.

It does what `baseline_runner e3` did, but retrieval, the context and the answer come from `rag_core`: the node filter
runs before ranking (H01), only active versions are searched (H04), the context is assembled within a budget, and every
citation is checked against the chunks that were given (H09). The grading rules (GR1 to GR5) and the metric summary are
the Phase 2 ones (`baseline_runner/grading.py`, `metrics.py`), so the two runs are graded the same way.

This is a plain module on top of the layers, like cli_issues.py: it may use the adapters and the Phase 2 harness.
The Phase 2 runner calls `run_core_e3` for `--engine core`.

Two phases, as in the baseline: retrieve for every question first, then answer every question, so the embedding model and the
language model are not swapped in and out of memory per question (the laptop has 4 GB of GPU memory).
"""
import json
import re
import time
from pathlib import Path

from baseline_runner import grading, metrics
from baseline_runner.config import METRICS, RESULTS
from baseline_runner.corpus import load_files, load_questions
from baseline_runner.experiments import write_csv
from baseline_runner.metrics import REFUSAL_TYPES

from .infrastructure.memory import InMemoryKnowledgeRepository, InMemoryVectorIndex
from .infrastructure.project_db import read_csv_file
from .infrastructure.sqlite import SqliteKnowledgeRepository
from .infrastructure.sqlite_vectors import SqliteVectorIndex
from .rag_wiring import load_hierarchy, prepare_case_study
from .workflows.question_answering import QuestionService

BASELINE_RUN = RESULTS / "e3-first"
NOT_MEASURED = "not measured"

# (key in the summary, metric id, name, direction). M24 has two numbers; M05 (faithfulness) needs the judge (Phase 10).
COMPARED = (
    ("M01", "M01", "Answer correctness", "higher"),
    ("M02", "M02", "Citation validity", "higher"),
    ("M03", "M03", "Correct refusal", "higher"),
    ("M04", "M04", "False refusal", "lower"),
    ("M05", "M05", "Answer faithfulness (needs the judge)", "higher"),
    ("M06", "M06", "Retrieval hit", "higher"),
    ("M07", "M07", "Context precision", "higher"),
    ("M08", "M08", "Context recall", "higher"),
    ("M09", "M09", "Version handling", "higher"),
    ("M22", "M22", "Time to first token, median (s)", "lower"),
    ("M23", "M23", "Generation speed, median (tokens/s)", "higher"),
    ("M24_median", "M24", "Question latency, median (s)", "lower"),
    ("M24_p90", "M24", "Question latency, 90th percentile (s)", "lower"),
)
ROW_BEGIN = ("llm", "question_id", "type", "asked_at_node", "answer", "cited", "correct", "refused",
             "ttft_s", "total_s", "wall_s", "tokens_per_s", "generated_tokens", "prompt_tokens", "gpu_mb", "ram_mb",
             "GR1", "GR2", "GR3", "GR4", "GR5", "embedding_model", "chunks", "k", "retrieved", "hit", "precision", "recall")
ROW_CORE_EXTRA = ("prompt", "refusal_reason", "invalid_citations", "chunk_ids_used", "chunk_ids_omitted")
ROW_COLUMNS = [*ROW_BEGIN, *ROW_CORE_EXTRA]


# ------------------------------------------------------------------ one run over the questions
def evaluate_questions(service, questions, facts, type_rules, stems, *, llm_id, embedding_id, chunks_name, k,
                       sampler=None, log=print):
    """Run the questions through a QuestionService and grade them. Returns (records, summary).

    A record has the columns of the Phase 2 e3_rows.csv, then the core's extra columns (ROW_CORE_EXTRA).
    A timing the model does not report (a stub model) is None, and the metric that needs it is None too."""
    sampler = sampler or (lambda: {})
    retrieved = {}
    for q in questions:                                         # phase 1: every question is embedded and searched
        start = time.perf_counter()
        hits = service.retrieve(q["question"], q["asked_at_node"], k)
        retrieved[q["question_id"]] = (hits, time.perf_counter() - start)

    records = []
    for q in questions:                                         # phase 2: every question is answered
        hits, retrieve_s = retrieved[q["question_id"]]
        start = time.perf_counter()
        answer = service.answer(q["question"], hits)
        wall_s = time.perf_counter() - start + retrieve_s
        stats = getattr(service.model, "last_stats", None) if answer.model_called else None
        results, cited = grading.grade_answer(q, facts[q["question_id"]], answer.text, type_rules, stems)
        shot = sampler()
        hit_stems = [h.chunk.location.source_stem for h in hits]
        groups = grading.gold_groups(q["source_files"], stems)
        hit, precision, recall = metrics.retrieval_scores(hit_stems, groups) if groups else (None, None, None)
        record = {"llm": llm_id, "question_id": q["question_id"], "type": q["type"], "asked_at_node": q["asked_at_node"],
                  "answer": answer.text, "cited": ";".join(cited), "correct": grading.is_correct(results),
                  "refused": grading.says_refusal(answer.text),
                  "ttft_s": stats.ttft_s if stats else None, "total_s": stats.total_s if stats else None, "wall_s": wall_s,
                  "tokens_per_s": stats.tokens_per_s if stats else None,
                  "generated_tokens": stats.generated_tokens if stats else None,
                  "prompt_tokens": stats.prompt_tokens if stats else None,
                  "gpu_mb": shot.get("gpu_mb"), "ram_mb": shot.get("ram_mb")}
        for rule in ("GR1", "GR2", "GR3", "GR4", "GR5"):
            record[rule] = results.get(rule)
        record.update({"embedding_model": embedding_id, "chunks": chunks_name, "k": k, "retrieved": ";".join(hit_stems),
                       "hit": hit, "precision": precision, "recall": recall,
                       "prompt": answer.prompt_id, "refusal_reason": answer.refusal_reason,
                       "invalid_citations": ";".join(answer.invalid_citations),
                       "chunk_ids_used": ";".join(answer.chunk_ids_used), "chunk_ids_omitted": ";".join(answer.chunk_ids_omitted)})
        records.append(record)
    log(f"core {llm_id}: {sum(r['correct'] for r in records)} of {len(records)} correct")
    summary = {"llm": llm_id, "embedding_model": embedding_id, "chunks": chunks_name, "k": k,
               **metrics.summarize_answers(records), **retrieval_summary(records)}
    return records, summary


def retrieval_summary(records):
    """M06 hit, M07 precision and M08 recall over the answerable questions, from the hit, precision and recall columns."""
    scored = [r for r in records if r["type"] not in REFUSAL_TYPES and r.get("hit") is not None]
    return {"M06": metrics.share(r["hit"] for r in scored), "M07": metrics.mean(r["precision"] for r in scored),
            "M08": metrics.mean(r["recall"] for r in scored)}


# ------------------------------------------------------------------ the baseline to compare with
def _number(text):
    try:
        return None if text in ("", None) else float(text)
    except ValueError:
        return None


def _rows_for(folder, names, llm_id):
    for name in names:
        path = Path(folder) / name
        if path.is_file():
            return [row for row in read_csv_file(path) if row.get("llm") == llm_id]
    return []


def load_baseline(folder=BASELINE_RUN, llm_id="phi4-mini", metrics_csv=METRICS / "metrics.csv"):
    """The Phase 2 numbers to compare with: {summary key: float}.

    First choice is the saved run (the regraded files when they exist, because they use the current key facts); M06 to
    M08 are computed from its rows in the same way as for the core run. If the run is not there, the `baseline` column
    of metrics/metrics.csv is used. A metric with no number stays out of the dict, and the table says "not measured"."""
    values = {}
    summary = _rows_for(folder, ("e3_summary_regraded.csv", "e3_summary.csv"), llm_id)
    if summary:
        values.update({key: _number(v) for key, v in summary[0].items() if re.fullmatch(r"M\d\d(_\w+)?", key)})
        rows = _rows_for(folder, ("e3_rows_regraded.csv", "e3_rows.csv"), llm_id)
        for row in rows:
            row["hit"] = {"True": True, "False": False}.get(row.get("hit"))
            row["precision"], row["recall"] = _number(row.get("precision")), _number(row.get("recall"))
        values.update(retrieval_summary(rows))
        return {k: v for k, v in values.items() if v is not None}
    if Path(metrics_csv).is_file():
        for row in read_csv_file(metrics_csv):
            numbers = re.findall(r"\d+(?:\.\d+)?", row["baseline"] or "")
            if not numbers:
                continue
            if row["metric_id"] == "M24" and len(numbers) >= 2:
                values["M24_median"], values["M24_p90"] = float(numbers[0]), float(numbers[1])
            else:
                values[row["metric_id"]] = float(numbers[0])
    return values


def compare(summary, baseline):
    """The comparison table: one row per compared metric, with the baseline, the core run, the change and a verdict.
    A number that is missing on either side is "not measured"; the verdict then is "not comparable"."""
    rows = []
    for key, metric_id, name, direction in COMPARED:
        old, new = baseline.get(key), summary.get(key)
        if old is None or new is None:
            change, verdict = "", "not comparable"
        else:
            change = round(new - old, 3)
            verdict = "same" if abs(new - old) < 0.0005 else ("better" if (new > old) == (direction == "higher") else "worse")
        label = key.replace("M24_", "M24 ") if key.startswith("M24") else metric_id
        rows.append({"metric": label, "name": name, "direction": direction,
                     "baseline": NOT_MEASURED if old is None else round(old, 3),
                     "core": NOT_MEASURED if new is None else round(new, 3), "change": change, "verdict": verdict})
    return rows


def comparison_text(rows, baseline_label, core_label):
    lines = [f"Comparison: core run ({core_label}) against the Phase 2 baseline ({baseline_label})",
             f"{'metric':<11}{'name':<40}{'baseline':>13}{'core':>13}{'change':>9}  verdict"]
    for r in rows:
        lines.append(f"{r['metric']:<11}{r['name']:<40}{r['baseline']!s:>13}{r['core']!s:>13}{r['change']!s:>9}  {r['verdict']}")
    return "\n".join(lines)


def comparison_markdown(rows, baseline_label, core_label):
    lines = ["# Core run against the Phase 2 baseline", "",
             f"- Core run: {core_label}", f"- Baseline: {baseline_label}", "",
             "| Metric | Name | Direction | Baseline | Core | Change | Verdict |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {r['metric']} | {r['name']} | {r['direction']} | {r['baseline']} | {r['core']} | {r['change']} | {r['verdict']} |")
    lines += ["", "The two runs differ in three ways on purpose: the core indexes only the active version of each document "
              "(no D10 v1, no D12 copy), it checks every citation against the chunks it gave the model (H09), and "
              "an answer with no valid citation becomes a refusal (decision A44). Read the differences with that in mind.", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------ the whole run into a results folder
def write_results(out_dir, records, summary, rows_compare, meta, baseline_label, core_label, name="e3"):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / f"{name}_rows.csv", records, ROW_COLUMNS)
    write_csv(out_dir / f"{name}_summary.csv", [summary])
    write_csv(out_dir / "comparison.csv", rows_compare)
    (out_dir / "comparison.md").write_text(comparison_markdown(rows_compare, baseline_label, core_label),
                                           encoding="utf-8", newline="\n")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8", newline="\n")


def run_evaluation(out_dir, embedder, model, prompt, *, llm_id, embedding_id, chunks_name, k, server_info=None,
                   baseline_folder=BASELINE_RUN, question_ids=None, sampler=None, ps=None, clock=None, hierarchy=None,
                   log=print, uncited_policy="refuse"):
    """Index the case study into out_dir/knowledge.sqlite, run the questions, grade, compare, and write the results.

    Returns (records, summary, comparison_rows). `embedder` and `model` are ports (real Ollama adapters, or fakes)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hierarchy = hierarchy or load_hierarchy()
    repository = SqliteKnowledgeRepository(out_dir / "knowledge.sqlite")
    index = SqliteVectorIndex(out_dir / "knowledge.sqlite")
    try:
        retriever, _, report = prepare_case_study(repository, index, embedder, hierarchy, policy=chunks_name, clock=clock)
        log(f"indexed: {report.eligible} chunks ({report.embedded} embedded, {report.kept} kept), policy {chunks_name}, "
            f"model {report.signature.embedding_model}")
        questions = [q for q in load_questions() if question_ids is None or q["question_id"] in question_ids]
        service = QuestionService(retriever, model, prompt, uncited_policy=uncited_policy)
        records, summary = evaluate_questions(
            service, questions, grading.load_key_facts(), grading.load_type_rules(), [f.stem for f in load_files()],
            llm_id=llm_id, embedding_id=embedding_id, chunks_name=chunks_name, k=k, sampler=sampler, log=log)
    finally:
        repository.close()
        index.close()
    baseline = load_baseline(baseline_folder, llm_id)
    rows_compare = compare(summary, baseline)
    meta = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), **(server_info or {}), "command": "evaluate", "engine": "core",
            "llm": llm_id, "embedding": embedding_id, "chunks": chunks_name, "k": k,
            "prompt": f"{prompt.prompt_id} v{prompt.version}", "uncited_policy": uncited_policy,
            "questions": len(records), "baseline": str(baseline_folder), "ollama_ps": ps() if ps else ""}
    write_results(out_dir, records, summary, rows_compare, meta, f"{baseline_folder}, {llm_id}", out_dir.name)
    return records, summary, rows_compare


# ------------------------------------------------------------------ the Phase 2 runner with --engine core
def run_core_e3(ctx, llm_ids, embedding_id, chunks_name, k, question_ids=None, name="e3", prompt_id="P01"):
    """`baseline_runner e3 --engine core`: retrieval and answering by the core, in memory, with the runner's own client.
    Returns the summary rows and writes <name>_rows.csv and <name>_summary.csv like the baseline engine does."""
    from .infrastructure.ollama_embedding import OllamaEmbeddingModel
    from .infrastructure.ollama_language import OllamaLanguageModel
    from .knowledge.chunking import POLICIES
    from .workflows.answer_prompts import load_answer_prompt
    if chunks_name not in POLICIES:
        raise ValueError(f"engine core cuts chunks with the core's policies {sorted(POLICIES)}, not {chunks_name!r}")
    embedder = OllamaEmbeddingModel(ctx.registry[embedding_id]["runtime_tag"], embedding_id, client=ctx.client,
                                    prompts=ctx.prompts)
    repository, index = InMemoryKnowledgeRepository(), InMemoryVectorIndex()
    retriever, _, report = prepare_case_study(repository, index, embedder, load_hierarchy(), policy=chunks_name)
    ctx.log(f"{name.upper()} core: indexed {report.eligible} chunks")
    prompt = load_answer_prompt(prompt_id, ctx.prompts.folder)
    questions = [q for q in ctx.questions if question_ids is None or q["question_id"] in question_ids]
    rows, summary = [], []
    for llm_id in llm_ids:
        think = False if ctx.registry[llm_id]["thinking_listed"] == "yes" else None
        model = OllamaLanguageModel(ctx.registry[llm_id]["runtime_tag"], client=ctx.client, options={}, think=think)
        records, row = evaluate_questions(QuestionService(retriever, model, prompt), questions, ctx.facts, ctx.type_rules,
                                          ctx.stems, llm_id=llm_id, embedding_id=embedding_id, chunks_name=chunks_name,
                                          k=k, sampler=ctx.sampler, log=ctx.log)
        rows += records
        summary.append(row)
    write_csv(ctx.out_dir / f"{name}_rows.csv", rows, ROW_COLUMNS)
    write_csv(ctx.out_dir / f"{name}_summary.csv", summary)
    return summary
