"""Turn graded answers and timings into the metrics of metrics/metrics.csv."""
import math
import statistics

REFUSAL_TYPES = {"unanswerable", "node_boundary"}


def share(flags):
    flags = list(flags)
    return sum(1 for f in flags if f) / len(flags) if flags else None


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def percentile(values, p):
    """Nearest-rank percentile: the value below which p percent of the values fall."""
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[max(math.ceil(p / 100 * len(values)), 1) - 1]


def retrieval_scores(retrieved_stems, groups):
    """M06 hit, M07 precision, M08 recall for one question, at file level.
    hit: some retrieved chunk is from an answer-key source. precision: the share of retrieved chunks that are.
    recall: the share of answer-key sources that appear among the retrieved chunks."""
    gold = set().union(*groups) if groups else set()
    in_gold = [stem in gold for stem in retrieved_stems]
    precision = sum(in_gold) / len(in_gold) if in_gold else 0.0
    covered = sum(1 for group in groups if group & set(retrieved_stems))
    recall = covered / len(groups) if groups else 0.0
    return any(in_gold), precision, recall


def summarize_answers(records):
    """records: one dict per question with question_id, type, correct, refused, GR4, GR5 and timings.
    Returns the metrics that a set of answers can give."""
    answerable = [r for r in records if r["type"] not in REFUSAL_TYPES]
    refusal = [r for r in records if r["type"] in REFUSAL_TYPES]
    only = lambda ids: [r for r in records if r["question_id"] in ids]
    return {
        "M01": share(r["correct"] for r in answerable),
        "M02": share(r["GR5"] for r in answerable),
        "M03": share(r["correct"] for r in refusal),
        "M04": share(r["refused"] for r in answerable),
        "M09": share(r["correct"] and r["GR5"] for r in only({"Q01", "Q02", "Q26"})),
        "M12": share(r["GR4"] for r in only({"Q03"})),
        "M14": share(r["correct"] and r["GR5"] for r in only({"Q20", "Q21"})),
        "M22": median(r["ttft_s"] for r in records),
        "M23": median(r["tokens_per_s"] for r in records),
        "M24_median": median(r["wall_s"] for r in records),
        "M24_p90": percentile([r["wall_s"] for r in records], 90),
        "M25_gpu_mb_max": max((r["gpu_mb"] for r in records if r.get("gpu_mb") is not None), default=None),
        "M25_ram_mb_max": max((r["ram_mb"] for r in records if r.get("ram_mb") is not None), default=None),
    }
