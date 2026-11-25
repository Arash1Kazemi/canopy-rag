"""The held-out question set (case_study/heldout_questions.csv) and the labelled duplicate pairs."""
import csv
import importlib.util
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
HELDOUT = PROJECT / "case_study" / "heldout_questions.csv"
ANSWER_KEY = PROJECT / "case_study" / "answer_key.csv"
DOCUMENTS = PROJECT / "case_study" / "documents"
PAIRS = PROJECT / "tests" / "fixtures" / "duplicates" / "pairs.csv"
COLUMNS = ["question_id", "asked_at_node", "language", "type", "question", "expected_answer", "source_files"]


def rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_heldout_file_is_utf8_lf_without_bom():
    data = HELDOUT.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in data
    data.decode("utf-8")


def test_heldout_columns_and_ids():
    with HELDOUT.open(encoding="utf-8", newline="") as f:
        assert next(csv.reader(f)) == COLUMNS
    ids = [r["question_id"] for r in rows(HELDOUT)]
    assert len(ids) == len(set(ids)) >= 10
    assert all(i.startswith("HQ") for i in ids)


def test_heldout_rows_are_complete_and_nodes_exist():
    node_ids = {p.name.split("_")[0] for p in DOCUMENTS.iterdir()}
    for r in rows(HELDOUT):
        assert all(r[c].strip() for c in COLUMNS), r["question_id"]
        assert r["asked_at_node"] in node_ids


def test_heldout_source_files_exist():
    stems = {p.stem for p in DOCUMENTS.rglob("*.md")}
    for r in rows(HELDOUT):
        for source in r["source_files"].split(","):
            source = source.split("(")[0].strip()
            if source and not source.startswith("none"):
                assert source in stems, (r["question_id"], source)


def test_unanswerable_questions_say_insufficient_knowledge():
    for r in rows(HELDOUT):
        if r["type"] == "unanswerable":
            assert r["expected_answer"].lower().startswith("insufficient knowledge")


def test_no_heldout_question_repeats_the_answer_key():
    key = {" ".join(r["question"].lower().split()) for r in rows(ANSWER_KEY)}
    for r in rows(HELDOUT):
        assert " ".join(r["question"].lower().split()) not in key, r["question_id"]


def test_no_code_mentions_the_heldout_file():
    """Nothing that tunes (the core, the baseline runner, the scripts) may read the held-out questions."""
    for folder in ("rag_core", "baseline_runner", "scripts"):
        for path in (PROJECT / folder).rglob("*.py"):
            assert "heldout_questions" not in path.read_text(encoding="utf-8"), path


# ---- labelled duplicate pairs -------------------------------------------------------------------------------------

def test_pairs_csv_is_valid_and_files_exist():
    data = PAIRS.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf") and b"\r" not in data
    with PAIRS.open(encoding="utf-8", newline="") as f:
        assert next(csv.reader(f)) == ["pair_id", "file_a", "file_b", "label", "note"]
    found = rows(PAIRS)
    ids = [r["pair_id"] for r in found]
    assert len(ids) == len(set(ids))
    for r in found:
        assert r["label"] in ("exact", "near", "overlap", "different"), r["pair_id"]
        for name in ("file_a", "file_b"):
            assert (PAIRS.parent / r[name]).is_file(), r[name]
        assert r["file_a"] != r["file_b"]
    labels = [r["label"] for r in found]
    assert labels.count("near") >= 8 and labels.count("overlap") >= 8 and labels.count("different") >= 8


def test_fixture_texts_are_not_in_the_case_study_folder():
    names = {p.name for p in DOCUMENTS.rglob("*.md")}
    for p in PAIRS.parent.glob("*.md"):
        assert p.name not in names


def test_labelled_mode_gives_the_expected_verdicts_for_clear_cases():
    spec = importlib.util.spec_from_file_location("duplicate_experiment", PROJECT / "scripts" / "duplicate_experiment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy = module.DuplicatePolicy()
    by_id = {r["pair_id"]: r for r in rows(PAIRS)}

    def verdict(pair_id):
        r = by_id[pair_id]
        return module.verdict_for((PAIRS.parent / r["file_a"]).read_text(encoding="utf-8"),
                                  (PAIRS.parent / r["file_b"]).read_text(encoding="utf-8"), policy)[0]

    exact = [p for p, r in by_id.items() if r["label"] == "exact"]
    different = [p for p, r in by_id.items() if r["label"] == "different"]
    assert all(verdict(p) == "exact" for p in exact)
    assert all(verdict(p) == "different" for p in different)
