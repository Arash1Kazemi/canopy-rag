import sqlite3
from contextlib import closing

from rag_core.__main__ import main
from rag_core.infrastructure.project_db import PROJECT, SEED_FOLDERS, migrate, project_rows, read_csv_file


def test_migration_matches_seed_rows_and_preserves_database_edits(tmp_path, monkeypatch):
    path = tmp_path / "project.sqlite"
    monkeypatch.setenv("RAG_DATA_DB", str(path))
    main(["migrate-db"])

    for folder in SEED_FOLDERS:
        for csv_path in (PROJECT / folder).glob("*.csv"):
            assert project_rows(csv_path) == read_csv_file(csv_path)

    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE nodes SET name = 'Renamed Council' WHERE node_id = 'N0'")
        db.execute("UPDATE case_study_answer_key SET question = 'Edited in SQLite' WHERE question_id = 'Q01'")
    migrate()
    assert next(row for row in project_rows(PROJECT / "case_study/answer_key.csv")
                if row["question_id"] == "Q01")["question"] == "Edited in SQLite"
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT name FROM nodes WHERE node_id = 'N0'").fetchone() == ("Renamed Council",)


def test_default_ingestion_uses_persisted_hierarchy_and_stores_knowledge(tmp_path, monkeypatch):
    path = tmp_path / "project.sqlite"
    monkeypatch.setenv("RAG_DATA_DB", str(path))
    monkeypatch.setattr("rag_core.__main__.RESULTS", tmp_path / "reports")
    assert main(["define-node", "--id", "N7", "--name", "Depot", "--parent", "N4", "--field", "depots"]) == 0
    source = tmp_path / "depot.txt"
    source.write_text("The depot opens at eight.", encoding="utf-8")
    assert main(["ingest-file", str(source), "--item", "D99", "--node", "N7",
                 "--version", "1", "--title", "Depot hours"]) == 0
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT node_id, active_tag FROM items WHERE item_id = 'D99'").fetchone() == ("N7", "1")
        assert db.execute("SELECT text FROM chunks WHERE item_id = 'D99'").fetchone() == ("The depot opens at eight.",)
