"""Load the case study: the 22 files and the 26 questions. The case study is read-only."""
import csv
from dataclasses import dataclass
from pathlib import Path

from .config import CASE


@dataclass(frozen=True)
class SourceFile:
    stem: str      # the file name without .md, for example D10_bus_fleet_inventory_v2. It is the citation id.
    doc_id: str    # D10
    node_id: str   # N4
    version: str
    text: str


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_files(case_dir=CASE):
    files = []
    for row in read_csv(Path(case_dir) / "documents_manifest.csv"):
        path = Path(case_dir) / "documents" / row["file"]
        files.append(SourceFile(stem=path.stem, doc_id=row["doc_id"], node_id=row["node_id"],
                                version=row["version"], text=path.read_text(encoding="utf-8")))
    return files


def load_questions(case_dir=CASE):
    return read_csv(Path(case_dir) / "answer_key.csv")
