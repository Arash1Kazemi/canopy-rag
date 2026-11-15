"""The experiments E1 to E6 of prompt_test_plan.md. Each one writes CSV files into one results folder.

The code talks to a `client` that has embed() and chat(). It can be the real OllamaClient or a FakeClient,
so the whole pipeline can be tested with no model.
"""
import base64
import csv
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import grading, metrics, system_info
from .chunking import make_chunks
from .config import (BASELINE_CHUNKS, BASELINE_K, CHUNK_CONFIGS, DEFAULT_READ_PAGE_PROMPT, EMBEDDING_PROMPTS,
                     KS, LATENCY_KS, LATENCY_QUESTIONS, PAGE_OPTIONS, READ_PAGE_PROMPTS, REGISTRY)
from .corpus import load_files, load_questions, read_csv
from .metrics import REFUSAL_TYPES
from .prompts import Prompts
from .retrieval import Index, search


@dataclass
class Context:
    client: object
    out_dir: Path
    files: list
    questions: list
    facts: dict
    type_rules: dict
    prompts: Prompts
    registry: dict
    sampler: Callable = system_info.snapshot
    ps: Callable = system_info.ollama_ps
    log: Callable = print

    @property
    def stems(self):
        return [f.stem for f in self.files]


def load_registry(path=REGISTRY):
    return {row["model_id"]: row for row in read_csv(path)}


def make_context(client, out_dir, **overrides):
    values = dict(client=client, out_dir=Path(out_dir), files=load_files(), questions=load_questions(),
                  facts=grading.load_key_facts(), type_rules=grading.load_type_rules(),
                  prompts=Prompts(), registry=load_registry())
    values.update(overrides)
    return Context(**values)


def write_csv(path, rows, columns=None):
    rows = list(rows)
    columns = columns or (list(rows[0]) if rows else [])
    path.parent.mkdir(parents=True, exist_ok=True)

    def cell(value):
        return "" if value is None else round(value, 3) if isinstance(value, float) else value

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: cell(row.get(c)) for c in columns})


def write_meta(ctx, **extra):
    meta = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "ollama_version": ctx.client.version(),
            "pulled_models": ctx.client.models(), **extra}
    (ctx.out_dir).mkdir(parents=True, exist_ok=True)
    (ctx.out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def thinking_off(ctx, model_id):
    """Models whose page lists a thinking mode get think=False, so speed and answers are comparable."""
    return False if ctx.registry[model_id]["thinking_listed"] == "yes" else None


# ------------------------------------------------------------------ retrieval
def embed_texts(ctx, model_id, texts, prompt_id):
    tag = ctx.registry[model_id]["runtime_tag"]
    rendered = [ctx.prompts.render(prompt_id, text=t) for t in texts]
    start = time.perf_counter()
    vectors = ctx.client.embed(tag, rendered).vectors
    return vectors, time.perf_counter() - start


def build_index(ctx, model_id, chunks):
    _, document_prompt = EMBEDDING_PROMPTS[model_id]
    vectors, seconds = embed_texts(ctx, model_id, [c.text for c in chunks], document_prompt)
    return Index(chunks, vectors), seconds


def query_vector(ctx, model_id, question_text):
    query_prompt, _ = EMBEDDING_PROMPTS[model_id]
    vectors, seconds = embed_texts(ctx, model_id, [question_text], query_prompt)
    return vectors[0], seconds


def run_e1(ctx, embedding_ids, chunk_names=tuple(CHUNK_CONFIGS), ks=KS):
    """E1: which embedding model puts the answer-key sources first? Gives M06, M07, M08."""
    answerable = [q for q in ctx.questions if q["type"] not in REFUSAL_TYPES]
    rows, summary = [], []
    for model_id in embedding_ids:
        for chunk_name in chunk_names:
            chunks = make_chunks(ctx.files, chunk_name)
            index, index_s = build_index(ctx, model_id, chunks)
            scores, query_s = {k: [] for k in ks}, 0.0
            for q in answerable:
                vector, seconds = query_vector(ctx, model_id, q["question"])
                query_s += seconds
                hits = search(index, vector, q["asked_at_node"], max(ks))
                groups = grading.gold_groups(q["source_files"], ctx.stems)
                for k in ks:
                    stems = [chunk.stem for chunk, _ in hits[:k]]
                    hit, precision, recall = metrics.retrieval_scores(stems, groups)
                    scores[k].append((hit, precision, recall))
                    rows.append({"embedding_model": model_id, "chunks": chunk_name, "k": k, "question_id": q["question_id"],
                                 "hit": hit, "precision": precision, "recall": recall, "retrieved": ";".join(stems)})
            ctx.log(f"E1 {model_id} {chunk_name}: indexed {len(chunks)} chunks in {index_s:.1f}s")
            for k in ks:
                summary.append({"embedding_model": model_id, "chunks": chunk_name, "k": k, "questions": len(scores[k]),
                                "M06_hit": metrics.share(s[0] for s in scores[k]),
                                "M07_precision": metrics.mean(s[1] for s in scores[k]),
                                "M08_recall": metrics.mean(s[2] for s in scores[k]),
                                "chunk_count": len(chunks), "index_s": index_s, "query_s_total": query_s})
    write_csv(ctx.out_dir / "e1_rows.csv", rows)
    write_csv(ctx.out_dir / "e1_summary.csv", summary)
    return summary


# ------------------------------------------------------------------ answering
def context_text(chunks):
    return "\n\n".join(f"[{c.stem}] {c.text}" for c in chunks)


def ask(ctx, llm_id, question, chunks, extra_s=0.0):
    """One question to one LLM with the given chunks. Returns one graded record."""
    registry_row = ctx.registry[llm_id]
    prompt = ctx.prompts.render("P01", context=context_text(chunks), question=question["question"])
    start = time.perf_counter()
    result = ctx.client.chat(registry_row["runtime_tag"], [{"role": "user", "content": prompt}], think=thinking_off(ctx, llm_id))
    wall_s = time.perf_counter() - start + extra_s
    results, cited = grading.grade_answer(question, ctx.facts[question["question_id"]], result.text, ctx.type_rules, ctx.stems)
    shot = ctx.sampler()
    record = {"llm": llm_id, "question_id": question["question_id"], "type": question["type"],
              "asked_at_node": question["asked_at_node"], "answer": result.text, "cited": ";".join(cited),
              "correct": grading.is_correct(results), "refused": grading.says_refusal(result.text),
              "ttft_s": result.stats.ttft_s, "total_s": result.stats.total_s, "wall_s": wall_s,
              "tokens_per_s": result.stats.tokens_per_s, "generated_tokens": result.stats.generated_tokens,
              "prompt_tokens": result.stats.prompt_tokens, "gpu_mb": shot.get("gpu_mb"), "ram_mb": shot.get("ram_mb")}
    for rule in ("GR1", "GR2", "GR3", "GR4", "GR5"):
        record[rule] = results.get(rule)
    return record


def oracle_chunks(ctx, question):
    """The full text of each answer-key source file: the best chunks retrieval could ever return."""
    by_stem = {c.stem: c for c in make_chunks(ctx.files, "file")}
    return [by_stem[sorted(group)[0]] for group in grading.gold_groups(question["source_files"], ctx.stems)]


def run_e2(ctx, llm_ids):
    """E2: each LLM answers from the right files, so a mistake is the LLM's, not retrieval's."""
    rows, summary = [], []
    for llm_id in llm_ids:
        records = []
        for q in ctx.questions:
            if q["type"] in REFUSAL_TYPES:
                continue
            records.append(ask(ctx, llm_id, q, oracle_chunks(ctx, q)))
        ctx.log(f"E2 {llm_id}: {sum(r['correct'] for r in records)} of {len(records)} correct")
        rows += records
        summary.append({"llm": llm_id, **metrics.summarize_answers(records)})
    write_csv(ctx.out_dir / "e2_rows.csv", rows)
    write_csv(ctx.out_dir / "e2_summary.csv", summary)
    return summary


def retrieve_for_all(ctx, embedding_id, chunk_name, k, questions):
    """Retrieve for every question first, so the embedding model is not swapped in and out of memory per question."""
    index, _ = build_index(ctx, embedding_id, make_chunks(ctx.files, chunk_name))
    found = {}
    for q in questions:
        vector, seconds = query_vector(ctx, embedding_id, q["question"])
        found[q["question_id"]] = ([chunk for chunk, _ in search(index, vector, q["asked_at_node"], k)], seconds)
    return found


def run_e3(ctx, llm_ids, embedding_id, chunk_name=BASELINE_CHUNKS, k=BASELINE_K, question_ids=None, name="e3"):
    """E3: the whole path: retrieve inside the node, then answer. Gives M01 to M04, M09, M12, M14, M22 to M25."""
    questions = [q for q in ctx.questions if question_ids is None or q["question_id"] in question_ids]
    found = retrieve_for_all(ctx, embedding_id, chunk_name, k, questions)
    rows, summary = [], []
    for llm_id in llm_ids:
        records = []
        for q in questions:
            chunks, embed_s = found[q["question_id"]]
            record = ask(ctx, llm_id, q, chunks, extra_s=embed_s)
            groups = grading.gold_groups(q["source_files"], ctx.stems)
            hit, precision, recall = metrics.retrieval_scores([c.stem for c in chunks], groups) if groups else (None, None, None)
            record.update({"embedding_model": embedding_id, "chunks": chunk_name, "k": k,
                           "retrieved": ";".join(c.stem for c in chunks), "hit": hit, "precision": precision, "recall": recall})
            records.append(record)
        ctx.log(f"{name.upper()} {llm_id}: {sum(r['correct'] for r in records)} of {len(records)} correct")
        rows += records
        summary.append({"llm": llm_id, "embedding_model": embedding_id, "chunks": chunk_name, "k": k,
                        **metrics.summarize_answers(records)})
    write_csv(ctx.out_dir / f"{name}_rows.csv", rows)
    write_csv(ctx.out_dir / f"{name}_summary.csv", summary)
    return summary


# ------------------------------------------------------------------ reading a page
def required_page_facts(ctx):
    """The key-fact groups of Q12 and Q13, without repeats: what D19 must give back when it is read from an image."""
    groups = []
    for qid in ("Q12", "Q13"):
        for group in ctx.facts[qid]["required"]:
            if group not in groups:
                groups.append(group)
    return groups


def run_e4(ctx, lvm_ids, image_paths):
    """E4: can an LVM read the scanned minutes? Gives M13."""
    groups = required_page_facts(ctx)
    rows = []
    for lvm_id in lvm_ids:
        prompt_id = READ_PAGE_PROMPTS.get(lvm_id, DEFAULT_READ_PAGE_PROMPT)
        for image_path in image_paths:
            image = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
            result = ctx.client.chat(ctx.registry[lvm_id]["runtime_tag"],
                                     [{"role": "user", "content": ctx.prompts.render(prompt_id)}],
                                     images=[image], options=PAGE_OPTIONS, think=thinking_off(ctx, lvm_id))
            text = grading.normalize(result.text)
            found = [g[0] for g in groups if any(alternative in text for alternative in g)]
            missing = [g[0] for g in groups if g[0] not in found]
            shot = ctx.sampler()
            rows.append({"lvm": lvm_id, "image": Path(image_path).name, "prompt": prompt_id, "facts_total": len(groups),
                         "facts_found": len(found), "M13": len(found) / len(groups), "missing": ";".join(missing),
                         "wall_s": result.stats.total_s, "tokens_per_s": result.stats.tokens_per_s,
                         "gpu_mb": shot.get("gpu_mb"), "ram_mb": shot.get("ram_mb"), "text": result.text})
            ctx.log(f"E4 {lvm_id} {Path(image_path).name}: {len(found)} of {len(groups)} facts")
    write_csv(ctx.out_dir / "e4_rows.csv", rows)
    return rows


# ------------------------------------------------------------------ the judge probe
def parse_verdict(text):
    try:
        verdict = json.loads(text).get("verdict")
    except (ValueError, AttributeError):
        verdict = None
    if verdict not in ("correct", "wrong"):
        match = re.search(r'verdict"?\s*[:=]\s*"?(correct|wrong)', text, re.I)
        verdict = match.group(1).lower() if match else "unparsed"
    return verdict


PROBE_SETTINGS = {"fixed": {}, "sampled": {"temperature": 0.7, "seed": None}}


def run_e5(ctx, llm_ids, probe_rows):
    """E5: can a small LLM tell a right answer from a wrong one, and say the same thing twice? Gives M20."""
    questions = {q["question_id"]: q for q in ctx.questions}
    rows, summary = [], []
    for llm_id in llm_ids:
        tag = ctx.registry[llm_id]["runtime_tag"]
        for setting, options in PROBE_SETTINGS.items():
            group = []
            for probe in probe_rows:
                q = questions[probe["question_id"]]
                prompt = ctx.prompts.render("P04", question=q["question"], reference=q["expected_answer"], candidate=probe["candidate"])
                verdicts = [parse_verdict(ctx.client.chat(tag, [{"role": "user", "content": prompt}], options=options,
                                                          think=thinking_off(ctx, llm_id), json_mode=True).text)
                            for _ in range(2)]
                wanted = "correct" if probe["label"] == "right" else "wrong"
                group.append({"llm": llm_id, "setting": setting, "probe_id": probe["probe_id"], "question_id": q["question_id"],
                              "label": probe["label"], "gr1_blind_spot": probe["gr1_blind_spot"], "verdict_1": verdicts[0],
                              "verdict_2": verdicts[1], "same": verdicts[0] == verdicts[1], "matches_label": verdicts[0] == wanted})
            rows += group
            blind = [r for r in group if r["gr1_blind_spot"] == "yes"]
            summary.append({"llm": llm_id, "setting": setting, "probes": len(group),
                            "accuracy": metrics.share(r["matches_label"] for r in group),
                            "M20_repeatability": metrics.share(r["same"] for r in group),
                            "unparsed": sum(r["verdict_1"] == "unparsed" for r in group),
                            "accuracy_on_blind_spots": metrics.share(r["matches_label"] for r in blind)})
            ctx.log(f"E5 {llm_id} {setting}: accuracy {summary[-1]['accuracy']:.2f}, repeatability {summary[-1]['M20_repeatability']:.2f}")
    write_csv(ctx.out_dir / "e5_rows.csv", rows)
    write_csv(ctx.out_dir / "e5_summary.csv", summary)
    return summary


# ------------------------------------------------------------------ speed and memory limits
def run_e6(ctx, llm_ids, embedding_id, chunk_name=BASELINE_CHUNKS, ks=LATENCY_KS, question_ids=LATENCY_QUESTIONS):
    """E6: how do speed and memory change as more chunks go into the prompt? Gives M22 to M25 against k."""
    questions = [q for q in ctx.questions if q["question_id"] in question_ids]
    rows, summary = [], []
    for k in ks:
        found = retrieve_for_all(ctx, embedding_id, chunk_name, k, questions)
        for llm_id in llm_ids:
            records = []
            for q in questions:
                chunks, embed_s = found[q["question_id"]]
                record = ask(ctx, llm_id, q, chunks, extra_s=embed_s)
                record.update({"k": k, "ollama_ps": ""})
                records.append(record)
            records[-1]["ollama_ps"] = ctx.ps()  # one reading per (model, k): the GPU and CPU split of the loaded model
            rows += records
            summary.append({"llm": llm_id, "k": k, **{key: value for key, value in metrics.summarize_answers(records).items()
                                                    if key in ("M22", "M23", "M24_median", "M24_p90", "M25_gpu_mb_max", "M25_ram_mb_max")},
                            "prompt_tokens_max": max(r["prompt_tokens"] for r in records)})
            ctx.log(f"E6 {llm_id} k={k}: median {summary[-1]['M24_median']:.1f}s")
    write_csv(ctx.out_dir / "e6_rows.csv", rows)
    write_csv(ctx.out_dir / "e6_summary.csv", summary)
    return summary


# ------------------------------------------------------------------ regrading saved answers
def _as_number(text, kind=float):
    return None if text in ("", None) else kind(float(text))


def regrade(ctx, run_dir, name):
    """Grade the saved answers of an e2 or e3 run again with the current key facts, without calling a model.
    Writes <name>_rows_regraded.csv and <name>_summary_regraded.csv next to the originals, which stay as they were."""
    run_dir = Path(run_dir)
    questions = {q["question_id"]: q for q in ctx.questions}
    rows = read_csv(run_dir / f"{name}_rows.csv")
    by_llm, regraded = {}, []
    for row in rows:
        q = questions[row["question_id"]]
        results, cited = grading.grade_answer(q, ctx.facts[q["question_id"]], row["answer"], ctx.type_rules, ctx.stems)
        record = dict(row)
        record.update({rule: results.get(rule) for rule in ("GR1", "GR2", "GR3", "GR4", "GR5")})
        record.update({"cited": ";".join(cited), "correct": grading.is_correct(results), "refused": grading.says_refusal(row["answer"]),
                       "was_correct": row["correct"]})
        for key in ("ttft_s", "total_s", "wall_s", "tokens_per_s"):
            record[key] = _as_number(row[key])
        for key in ("gpu_mb", "ram_mb", "generated_tokens", "prompt_tokens"):
            record[key] = _as_number(row[key], int)
        regraded.append(record)
        by_llm.setdefault(row["llm"], []).append(record)
    write_csv(run_dir / f"{name}_rows_regraded.csv", regraded)
    summary = [{"llm": llm, **metrics.summarize_answers(records)} for llm, records in by_llm.items()]
    write_csv(run_dir / f"{name}_summary_regraded.csv", summary)
    return summary
