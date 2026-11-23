"""Import the project datasets once and read them from SQLite."""
import csv
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .registry_csv import hierarchy_from_rows
from .sqlite_hierarchy import SqliteHierarchyRepository

PROJECT = Path(__file__).resolve().parents[2]
SEED_FOLDERS = ("architecture", "case_study", "experiments", "glossary", "metrics",
                "models", "prompts", "registry", "scope")


def database_path():
    return Path(os.environ.get("RAG_DATA_DB", PROJECT / "data" / "project.sqlite"))


def read_csv_file(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def table_name(relative_path):
    return str(relative_path.with_suffix("")).replace("/", "_").replace("\\", "_")


def identifier(name):
    return '"' + name.replace('"', '""') + '"'


def migrate(path=None, *, source=PROJECT):
    """Seed a database in one transaction. Existing hierarchy edits win."""
    path = database_path() if path is None else Path(path)
    with closing(SqliteHierarchyRepository(path)) as repository:
        db = repository.db
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS seed_datasets (path TEXT PRIMARY KEY)")
            if db.execute("SELECT 1 FROM seed_datasets LIMIT 1").fetchone():
                return path
            for folder in SEED_FOLDERS:
                for file in sorted((source / folder).glob("*.csv")):
                    relative = file.relative_to(source)
                    table = identifier(table_name(relative))
                    with file.open(encoding="utf-8", newline="") as handle:
                        reader = csv.reader(handle)
                        columns = next(reader)
                        fields = ", ".join(f"{identifier(column)} TEXT NOT NULL" for column in columns)
                        db.execute(f"CREATE TABLE {table} ({fields})")
                        placeholders = ", ".join("?" for _ in columns)
                        db.executemany(f"INSERT INTO {table} VALUES ({placeholders})", reader)
                    db.execute("INSERT INTO seed_datasets VALUES (?)", (relative.as_posix(),))
            if repository.is_empty():
                nodes = _rows(db, Path("registry/node_layer_registry.csv"))
                layers = _rows(db, Path("registry/layer_registry.csv"))
                repository._replace(hierarchy_from_rows(nodes, layers))
    return path


def _rows(db, relative):
    db.row_factory = sqlite3.Row
    return [dict(row) for row in db.execute(f"SELECT * FROM {identifier(table_name(relative))} ORDER BY rowid")]


def project_rows(path):
    """Use SQLite for project datasets and CSV for explicit external inputs."""
    path = Path(path)
    relative = path.resolve().relative_to(PROJECT) if path.resolve().is_relative_to(PROJECT) else None
    if relative is None or len(relative.parts) != 2 or relative.parts[0] not in SEED_FOLDERS:
        return read_csv_file(path)
    database = database_path()
    if not database.is_file():
        migrate(database)
    with closing(sqlite3.connect(database)) as db:
        seeded = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'seed_datasets'"
        ).fetchone()
        if seeded:
            return _rows(db, relative)
    migrate(database)
    with closing(sqlite3.connect(database)) as db:
        return _rows(db, relative)
