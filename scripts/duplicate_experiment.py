"""Phase 5 experiment: how do word-group measures behave? Run from UNI-Project/:

    ../.venv/bin/python.exe -I scripts/duplicate_experiment.py

Four parts, all on the case-study documents (they are only read, never changed):
  A  different documents      the highest resemblance and containment between two DIFFERENT city documents
  B  edited copies            a document with 1%..40% of its words replaced (seeded, so the run is repeatable)
  C  a passage inside another a passage of 10..160 words of one document inserted into another document
  D  a format copy            a Markdown file, written as DOCX and read back
It writes results/duplicates/phase5-experiment/experiment.csv.

Labelled mode (metrics M10 and M11 baselines):

    ../.venv/bin/python.exe -I scripts/duplicate_experiment.py --pairs tests/fixtures/duplicates/pairs.csv

It runs the detector on each labelled pair (exact | near | overlap | different) and writes the verdict of each pair and the
precision and recall per label to results/duplicates/labelled-pairs/. The numbers are baselines, not targets. The numbers come from a small, planted data set: use them
to see how the measures behave, not as a final choice of limits. Metrics M10 and M11 need more planted pairs.
"""
import csv
import datetime
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from rag_core.infrastructure.memory import InMemoryKnowledgeRepository          # noqa: E402
from rag_core.infrastructure.registry_csv import CsvHierarchyRepository         # noqa: E402
from rag_core.ingestion.case_study import manifest_requests                     # noqa: E402
from rag_core.ingestion.extractors import DocxExtractor, Extractors             # noqa: E402
from rag_core.ingestion.samples import markdown_to_docx                         # noqa: E402
from rag_core.ingestion.service import IngestionService                         # noqa: E402
from rag_core.knowledge.duplicates import DuplicatePolicy, containment, resemblance, word_groups  # noqa: E402
from rag_core.knowledge.model import ContentHash                                # noqa: E402

LABELS = ("exact", "near", "overlap", "different")

SIZES = (3, 5, 8)
RATES = (0.01, 0.02, 0.05, 0.10, 0.20, 0.40)
PASSAGES = (10, 20, 40, 80, 160)
SEEDS = range(5)
ROWS = []


def row(experiment, case, size, res, con, shared="", note=""):
    ROWS.append({"experiment": experiment, "case": case, "word_group_size": size, "resemblance": f"{res:.3f}",
                 "containment": f"{con:.3f}", "shared_groups": shared, "note": note})


def load_texts():
    hierarchy = CsvHierarchyRepository(PROJECT / "registry" / "node_layer_registry.csv").load()
    repo = InMemoryKnowledgeRepository()
    service = IngestionService(hierarchy, repo, Extractors())
    for request in manifest_requests(PROJECT / "case_study"):
        service.register(request)
    return {str(i.item_id): i.active_version.text for i in repo.all_items()}


def part_a(texts):
    print("A. different documents (20 items, 190 pairs)")
    ids = sorted(texts)
    for size in SIZES:
        groups = {i: word_groups(texts[i], size) for i in ids}
        pairs = [(resemblance(groups[a], groups[b]), containment(groups[a], groups[b]), len(groups[a] & groups[b]), a, b)
                 for n, a in enumerate(ids) for b in ids[n + 1:]]
        best_r, best_c = max(pairs), max(pairs, key=lambda p: p[1])
        print(f"   size {size}: highest resemblance {best_r[0]:.3f} ({best_r[3]} vs {best_r[4]}), "
              f"highest containment {best_c[1]:.3f} ({best_c[3]} vs {best_c[4]}, {best_c[2]} shared groups)")
        row("A different documents", f"{best_r[3]} vs {best_r[4]} (highest resemblance)", size, best_r[0], best_r[1], best_r[2])
        row("A different documents", f"{best_c[3]} vs {best_c[4]} (highest containment)", size, best_c[0], best_c[1], best_c[2])
        if size == 5:
            for r_, c_, s_, a, b in sorted(pairs, reverse=True)[:5]:
                print(f"      top resemblance  {a} vs {b}: {r_:.3f} (containment {c_:.3f}, {s_} shared)")


def part_b(texts, source):
    print(f"B. edited copies of {source} ({len(texts[source].split())} words), mean of {len(SEEDS)} seeds")
    words = texts[source].split()
    for size in SIZES:
        base = word_groups(texts[source], size)
        for rate in RATES:
            res = []
            con = []
            kinds = Counter()
            for seed in SEEDS:
                rng = random.Random(seed)
                edited = list(words)
                for n, at in enumerate(rng.sample(range(len(edited)), max(1, round(rate * len(edited))))):
                    edited[at] = f"zz{n}"
                groups = word_groups(" ".join(edited), size)
                res.append(resemblance(base, groups))
                con.append(containment(base, groups))
                kind = DuplicatePolicy(word_group_size=size).kind_for(res[-1], len(base & groups))
                kinds[kind.value if kind else "none"] += 1
            verdict = ", ".join(f"{k} {n}" for k, n in sorted(kinds.items()))
            row("B edited copy", f"{rate:.0%} of words replaced", size, sum(res) / len(res), sum(con) / len(con),
                note=f"kind in {len(SEEDS)} seeds: {verdict}")
            if size == 5:
                print(f"   {rate:>4.0%} of words replaced: resemblance {sum(res) / len(res):.3f}, "
                      f"containment {sum(con) / len(con):.3f}  -> {verdict}")


def part_c(texts, source, host):
    print(f"C. a passage of {source} inserted into the middle of {host}")
    src, hst = texts[source].split(), texts[host].split()
    policy = DuplicatePolicy()
    for length in PASSAGES:
        start = len(src) // 3
        passage = src[start:start + length]
        merged = hst[:len(hst) // 2] + passage + hst[len(hst) // 2:]
        a, b = word_groups(texts[source], policy.word_group_size), word_groups(" ".join(merged), policy.word_group_size)
        shared = len(a & b)
        kind = policy.kind_for(resemblance(a, b), shared)
        note = f"{len(passage)} words inserted -> {kind.value if kind else 'none'}"
        row("C passage inside another", f"{source} in {host}", policy.word_group_size, resemblance(a, b), containment(a, b), shared, note)
        print(f"   {len(passage):>3} words inserted: containment {containment(a, b):.3f}, resemblance {resemblance(a, b):.3f}, "
              f"{shared} shared groups -> {kind.value if kind else 'none'}")


def part_d(texts, source):
    print(f"D. {source}: Markdown written as DOCX and read back")
    with tempfile.TemporaryDirectory() as folder:
        docx = markdown_to_docx(texts[source], Path(folder) / "copy.docx")
        back = DocxExtractor().extract(docx).text
    for size in SIZES:
        a, b = word_groups(texts[source], size), word_groups(back, size)
        row("D format copy", f"{source} as DOCX", size, resemblance(a, b), containment(a, b), len(a & b))
        print(f"   size {size}: resemblance {resemblance(a, b):.3f}")


def verdict_for(text_a, text_b, policy):
    """The detector's verdict for two texts, as the detector decides it: exact first, then near, then overlap."""
    if ContentHash.of_text(text_a) == ContentHash.of_text(text_b):
        return "exact", 1.0, 0, 1.0
    a, b = word_groups(text_a, policy.word_group_size), word_groups(text_b, policy.word_group_size)
    res, shared = resemblance(a, b), len(a & b)
    kind = policy.kind_for(res, shared)
    return (kind.value if kind else "different"), res, shared, containment(a, b)


def labelled_pairs(pairs_path, run_date=None):
    """Compare the detector's verdict with the label of each pair and save precision and recall per label."""
    pairs_path = Path(pairs_path)
    folder = pairs_path.parent
    policy = DuplicatePolicy()
    rows = []
    with pairs_path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            text_a = (folder / r["file_a"]).read_text(encoding="utf-8")
            text_b = (folder / r["file_b"]).read_text(encoding="utf-8")
            verdict, res, shared, con = verdict_for(text_a, text_b, policy)
            rows.append({"pair_id": r["pair_id"], "label": r["label"], "verdict": verdict, "resemblance": f"{res:.3f}",
                         "containment": f"{con:.3f}", "shared_groups": shared, "correct": str(verdict == r["label"]).lower(),
                         "note": r["note"]})
    summary = []
    for label in LABELS:
        actual = sum(1 for r in rows if r["label"] == label)
        predicted = sum(1 for r in rows if r["verdict"] == label)
        hits = sum(1 for r in rows if r["label"] == label and r["verdict"] == label)
        summary.append({"label": label, "pairs": actual, "predicted": predicted, "correct": hits,
                        "precision": f"{hits / predicted:.3f}" if predicted else "n/a",
                        "recall": f"{hits / actual:.3f}" if actual else "n/a"})
    # M11 reading: pairs labelled different that the detector flagged as exact (the count M11 asks for), and as any kind
    flagged_exact = sum(1 for r in rows if r["label"] == "different" and r["verdict"] == "exact")
    flagged_any = sum(1 for r in rows if r["label"] == "different" and r["verdict"] != "different")
    out = PROJECT / "results" / "duplicates" / "labelled-pairs"
    out.mkdir(parents=True, exist_ok=True)
    for name, data in (("pair_verdicts.csv", rows), ("precision_recall.csv", summary)):
        with (out / name).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, list(data[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
    run_date = run_date or datetime.date.today().isoformat()
    info = [f"run date: {run_date}",
            f"pairs file: {pairs_path.name} ({len(rows)} pairs)",
            f"policy: word groups of {policy.word_group_size}, near at {policy.near_limit}, overlap at {policy.min_shared_groups} shared groups",
            f"M11 (different pairs flagged as exact): {flagged_exact}",
            f"different pairs flagged as any kind: {flagged_any}",
            "these numbers are baselines, not targets"]
    (out / "run_info.txt").write_text("\n".join(info) + "\n", encoding="utf-8", newline="\n")
    print(f"labelled pairs: {len(rows)} (run date {run_date})")
    for r in rows:
        print(f"   {r['pair_id']} label {r['label']:<9} verdict {r['verdict']:<9} resemblance {r['resemblance']} shared {r['shared_groups']}")
    for s_ in summary:
        print(f"   {s_['label']:<9} pairs {s_['pairs']} predicted {s_['predicted']} correct {s_['correct']} "
              f"precision {s_['precision']} recall {s_['recall']}")
    print(f"different pairs flagged as exact: {flagged_exact}; as any kind: {flagged_any}")
    print(f"written: {out}")
    return rows, summary


def main():
    if "--pairs" in sys.argv:
        at = sys.argv.index("--pairs")
        run_date = sys.argv[sys.argv.index("--run-date") + 1] if "--run-date" in sys.argv else None
        labelled_pairs(PROJECT / sys.argv[at + 1] if not Path(sys.argv[at + 1]).is_absolute() else sys.argv[at + 1], run_date)
        return
    texts = load_texts()
    longest = sorted(texts, key=lambda i: len(texts[i].split()), reverse=True)
    part_a(texts)
    part_b(texts, longest[0])
    part_c(texts, longest[0], longest[1])
    part_d(texts, longest[0])
    out = PROJECT / "results" / "duplicates" / "phase5-experiment"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "experiment.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, list(ROWS[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(ROWS)
    print(f"written: {out / 'experiment.csv'}")


if __name__ == "__main__":
    main()
