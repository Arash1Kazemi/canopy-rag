"""Test area: the commands list-executors, match-executors, map-executor, ike-seed and ike-summary (Phase 9).
No model and no network: each test uses its own database file in tmp_path. Pinned: the seed people appear on first use,
the match output is the same on every run and shows the reasons, mapping is saved on the issue, the seed is idempotent,
and an unknown node, issue or executor gives exit code 2.
"""
import csv

import pytest

from rag_core.__main__ import main


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "project.sqlite"
    assert main(["migrate-db", "--db", str(path)]) == 0
    return str(path)


def test_list_executors_seeds_the_six_people(db, capsys):
    assert main(["list-executors", "--db", db]) == 0
    out = capsys.readouterr().out
    for person in ("P01", "P02", "P03", "P04", "P05", "P06"):
        assert person in out
    assert "wrote: D15" in out                         # the documents P01 wrote are found


def test_list_executors_of_one_node(db, capsys):
    assert main(["list-executors", "--db", db, "--node", "N6"]) == 0
    out = capsys.readouterr().out
    assert "P01" in out and "P03" in out and "P04" in out
    assert "P02" not in out and "P05" not in out


def test_seeding_twice_adds_nobody(db, capsys):
    main(["list-executors", "--db", db])
    first = capsys.readouterr().out
    main(["list-executors", "--db", db])
    assert capsys.readouterr().out == first


def test_match_executors_explains_the_score(db, capsys):
    assert main(["match-executors", "--db", db, "--issue", "I01"]) == 0
    out = capsys.readouterr().out
    assert "P01 Maryam Nazari" in out and "70 of 100" in out
    assert "route planning: route" in out and "bus intervals: bus" in out
    assert "D15" in out and "D17" in out


def test_match_output_is_the_same_on_every_run(db, capsys):
    main(["match-executors", "--db", db, "--issue", "I01", "--scope", "lineage"])
    first = capsys.readouterr().out
    main(["match-executors", "--db", db, "--issue", "I01", "--scope", "lineage"])
    assert capsys.readouterr().out == first


def test_match_limit_keeps_the_first_ranks(db, capsys):
    assert main(["match-executors", "--db", db, "--issue", "I01", "--scope", "lineage", "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert "1. P01" in out and "2. " not in out


def test_match_with_unknown_issue_is_exit_code_2(db, capsys):
    assert main(["match-executors", "--db", db, "--issue", "I99"]) == 2
    assert "I99" in capsys.readouterr().err


def test_map_executor_is_saved_on_the_issue(db, capsys):
    assert main(["map-executor", "--db", db, "--issue", "I01", "--executor", "P01"]) == 0
    assert "mapped" in capsys.readouterr().out
    assert main(["show-issue", "--db", db, "--id", "I01"]) == 0
    assert main(["map-executor", "--db", db, "--issue", "I01", "--executor", "P01"]) == 1      # already mapped
    assert "already mapped" in capsys.readouterr().err


def test_map_executor_outside_the_lineage_is_refused(db, capsys):
    assert main(["map-executor", "--db", db, "--issue", "I01", "--executor", "P05"]) == 1       # P05 is in N2
    assert "not the node of issue" in capsys.readouterr().err


def test_map_with_unknown_issue_or_executor_is_exit_code_2(db):
    assert main(["map-executor", "--db", db, "--issue", "I99", "--executor", "P01"]) == 2
    assert main(["map-executor", "--db", db, "--issue", "I01", "--executor", "P99"]) == 2


def test_list_executors_with_unknown_node_is_exit_code_2(db, capsys):
    assert main(["list-executors", "--db", db, "--node", "N9"]) == 2
    assert "N9" in capsys.readouterr().err


def test_ike_seed_loads_38_relations_once(db, capsys):
    assert main(["ike-seed", "--db", db]) == 0
    assert "38 relation(s) added, 0 already stored" in capsys.readouterr().out
    assert main(["ike-seed", "--db", db]) == 0
    assert "0 relation(s) added, 38 already stored" in capsys.readouterr().out


def test_ike_summary_and_csv_files(db, tmp_path, capsys):
    main(["ike-seed", "--db", db])
    capsys.readouterr()
    counts, edges = tmp_path / "out" / "counts.csv", tmp_path / "out" / "edges.csv"
    assert main(["ike-summary", "--db", db, "--node", "N6", "--csv-out", str(counts), "--edges-out", str(edges)]) == 0
    out = capsys.readouterr().out
    assert "IKE relation summary for N6 Bus Network Project" in out and "executor_has_expertise: 6" in out
    with counts.open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.reader(handle))) == 13            # header and the twelve relation types
    with edges.open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.reader(handle))) == 30            # header and the 29 relations of N6
    assert b"\r" not in edges.read_bytes()


def test_ike_summary_is_the_same_on_every_run(db, capsys):
    main(["ike-seed", "--db", db])
    capsys.readouterr()
    main(["ike-summary", "--db", db, "--node", "N6"])
    first = capsys.readouterr().out
    main(["ike-summary", "--db", db, "--node", "N6"])
    assert capsys.readouterr().out == first


def test_ike_summary_with_unknown_node_is_exit_code_2(db, capsys):
    assert main(["ike-summary", "--db", db, "--node", "N9"]) == 2
    assert "N9" in capsys.readouterr().err


def test_commands_on_a_file_without_hierarchy_are_exit_code_2(tmp_path, capsys):
    empty = str(tmp_path / "empty.sqlite")
    assert main(["list-executors", "--db", empty]) == 2
    assert main(["ike-summary", "--db", empty, "--node", "N6"]) == 2
