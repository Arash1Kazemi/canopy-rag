"""Judge scores in a SQLite file (Phase 10). By default the file is data/project.sqlite, next to the hierarchy and issues.

`add_run` stores all repeats of one run in one transaction: if one row fails, none is kept. A stored score is never changed.
Lists and score pairs are stored as JSON text; a boolean as 0 or 1.
"""
import json
import sqlite3
from pathlib import Path

from ..judging.model import JudgeScore
from .memory_judging import check_group

SCHEMA = """
CREATE TABLE IF NOT EXISTS judge_scores (
    run_id              TEXT NOT NULL,
    repeat              INTEGER NOT NULL,
    prompt_id           TEXT NOT NULL,
    prompt_version      INTEGER NOT NULL,
    rubric_id           TEXT NOT NULL,
    rubric_version      INTEGER NOT NULL,
    model_tag           TEXT NOT NULL,
    target_layer        INTEGER NOT NULL,
    threshold           INTEGER NOT NULL,
    text_sha256         TEXT NOT NULL,
    source_ref          TEXT NOT NULL,
    raw_output          TEXT NOT NULL,
    parse_ok            INTEGER NOT NULL,
    parse_error         TEXT NOT NULL,
    scores              TEXT NOT NULL,
    total               INTEGER,
    explanation         TEXT NOT NULL,
    missing_information TEXT NOT NULL,
    unsupported_claims  TEXT NOT NULL,
    suggested_fix       TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    judged_at           TEXT NOT NULL,
    PRIMARY KEY (run_id, repeat)
);
"""
COLUMNS = ["run_id", "repeat", "prompt_id", "prompt_version", "rubric_id", "rubric_version", "model_tag", "target_layer", "threshold",
           "text_sha256", "source_ref", "raw_output", "parse_ok", "parse_error", "scores", "total", "explanation",
           "missing_information", "unsupported_claims", "suggested_fix", "outcome", "judged_at"]


def row_of_score(score):
    row = {c: getattr(score, c) for c in COLUMNS}
    row["parse_ok"] = 1 if score.parse_ok else 0
    for name in ("scores", "missing_information", "unsupported_claims"):
        row[name] = json.dumps([list(p) if name == "scores" else p for p in getattr(score, name)], ensure_ascii=False)
    return row


def score_of_row(row):
    values = dict(row)
    values["parse_ok"] = bool(values["parse_ok"])
    values["scores"] = tuple((key, points) for key, points in json.loads(values["scores"]))
    values["missing_information"] = tuple(json.loads(values["missing_information"]))
    values["unsupported_claims"] = tuple(json.loads(values["unsupported_claims"]))
    return JudgeScore(**values)


class SqliteJudgeRepository:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def add_run(self, scores):
        group = check_group(scores)
        run_id = group[0].run_id
        if self.db.execute("SELECT 1 FROM judge_scores WHERE run_id = ?", (run_id,)).fetchone():
            raise ValueError(f"run {run_id} is already stored, so nothing was saved")
        with self.db:
            for score in group:
                row = row_of_score(score)
                self.db.execute(f"INSERT INTO judge_scores ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})",
                                [row[c] for c in COLUMNS])

    def _rows(self, where="", args=()):
        cursor = self.db.execute(f"SELECT {', '.join(COLUMNS)} FROM judge_scores {where} ORDER BY rowid", args)
        return [score_of_row(zip(COLUMNS, r)) for r in cursor]

    def run(self, run_id):
        return sorted(self._rows("WHERE run_id = ?", (run_id,)), key=lambda s: s.repeat)

    def run_ids(self):
        return [r[0] for r in self.db.execute("SELECT run_id FROM judge_scores GROUP BY run_id ORDER BY MIN(rowid)")]

    def all_scores(self):
        return self._rows()

    def close(self):
        self.db.close()
