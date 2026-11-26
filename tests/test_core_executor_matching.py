"""Test area: Phase 9 executor matching and the executor workflows. The same tests run with in-memory and SQLite
repositories (build plan rule 10). No model is needed."""
import pytest

from executor_builders import executor, people, service, weights
from issue_builders import issue, seed_issues
from issue_builders import weights as progress_weights
from rag_core.executors.matching import MatchWeights, rank_executors
from rag_core.infrastructure.memory import InMemoryExecutorRepository, InMemoryIssueRepository
from rag_core.infrastructure.sqlite_executors import SqliteExecutorRepository
from rag_core.infrastructure.sqlite_issues import SqliteIssueRepository
from rag_core.issues.progress import compute_progress, progress_factors
from rag_core.workflows.executors import FAILED, MAPPED, MATCHED


@pytest.fixture(params=["memory", "sqlite"])
def repos(request, tmp_path):
    if request.param == "memory":
        yield InMemoryExecutorRepository(), InMemoryIssueRepository()
    else:
        e, i = SqliteExecutorRepository(tmp_path / "e.sqlite"), SqliteIssueRepository(tmp_path / "i.sqlite")
        yield e, i
        e.close()
        i.close()


def make(repos, **kwargs):
    return service(executor_repo=repos[0], issue_repo=repos[1], **kwargs)


def ids(result):
    return list(result.executor_ids)


def test_for_i01_the_route_planner_ranks_first(repos):
    result = make(repos).match_executors("I01")
    assert result.outcome == MATCHED and ids(result)[0] == "P01"
    assert ids(result) == ["P01"]            # in the node N6 only the planner shares a word with the issue


def test_the_explanation_lists_the_matched_tags_and_every_component(repos):
    top = make(repos).match_executors("I01").matches[0]
    assert dict(top.matched_tags) == {"bus intervals": ("bus",), "route planning": ("route",)}
    assert [c.name for c in top.components] == ["tags", "documents", "same_node", "availability"]
    assert top.component("tags").detail == ("bus intervals: bus", "route planning: route")
    assert {d[0] for d in top.matched_documents} == {"D15", "D17"}      # "Route Redesign ...", "Route 7 Pilot Test Report"
    # the parts add up to the score: tags 60 * 0.5 + documents 25 + same node 15 + availability 0
    assert top.score == 70 == round(sum(c.points for c in top.components), 2)
    text = "\n".join(top.explain())
    assert "route planning: route" in text and "P01 Maryam Nazari" in text


def test_the_ranking_is_the_same_on_every_run(repos):
    s = make(repos)
    runs = [s.match_executors("I01", scope="lineage", include_unmatched=True).executor_ids for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_the_order_of_the_stored_executors_does_not_change_the_ranking():
    forward = rank_executors(issue(), [executor("P91"), executor("P92", expertise=("bus", "routes"))], weights())
    backward = rank_executors(issue(), [executor("P92", expertise=("bus", "routes")), executor("P91")], weights())
    assert [m.executor_id for m in forward] == [m.executor_id for m in backward]


def test_a_tie_is_broken_by_executor_id_not_by_name_or_order():
    twins = [executor("P12", name="Zed"), executor("P02", name="Yan"), executor("P10", name="Abe")]
    ranked = rank_executors(issue(title="Bus routes", description="bus routes"), twins, weights())
    assert len({m.score for m in ranked}) == 1
    assert [str(m.executor_id) for m in ranked] == ["P02", "P10", "P12"]      # numeric: P02 < P10 < P12


def test_a_better_tag_cover_ranks_higher():
    narrow = executor("P01", expertise=("bus routes", "water losses", "air quality"))
    exact = executor("P02", expertise=("bus routes",))
    ranked = rank_executors(issue(title="Bus routes crowded", description="x"), [narrow, exact], weights())
    assert [str(m.executor_id) for m in ranked] == ["P02", "P01"]


def test_an_executor_without_a_reason_is_left_out_unless_everyone_is_asked_for():
    others = [executor("P01", expertise=("air quality",))]
    assert rank_executors(issue(), others, weights()) == []
    everyone = rank_executors(issue(), others, weights(), include_unmatched=True)
    assert [str(m.executor_id) for m in everyone] == ["P01"]
    assert everyone[0].component("tags").detail == ("no tag matched",)


def test_availability_counts_only_when_its_weight_is_above_zero():
    one = executor("P01", availability="available")
    two = executor("P02", availability="unavailable")
    same = rank_executors(issue(title="Bus routes"), [one, two], weights())
    assert same[0].score == same[1].score
    used = MatchWeights.of({"tags": 50, "documents": 20, "same_node": 15, "availability": 15})
    ranked = rank_executors(issue(title="Bus routes"), [two, one], used)
    assert [str(m.executor_id) for m in ranked] == ["P01", "P02"]
    assert ranked[0].component("availability").points == 15


def test_a_document_on_the_topic_adds_to_the_score():
    writer = executor("P01", expertise=("water",), documents_written=(("D15", "Route Redesign Pilot"),))
    ranked = rank_executors(issue(title="Route 7 overcrowded"), [writer], weights())
    assert ranked[0].component("documents").share == 1 and ranked[0].matched_tags == ()


def test_the_weights_must_add_up_to_100():
    with pytest.raises(Exception, match="100"):
        MatchWeights.of({"tags": 50, "documents": 20, "same_node": 15, "availability": 0})


def test_the_default_scope_is_the_issues_node_only(repos):
    s = make(repos)
    s.executors.add_all([executor("P50", node="N3", expertise=("bus routes",))])      # another branch
    result = s.match_executors("I01", include_unmatched=True)
    assert ids(result) == ["P01", "P03", "P04"]


def test_the_lineage_scope_adds_ancestors_and_descendants_but_not_other_branches(repos):
    s = make(repos)
    s.executors.add_all([executor("P50", node="N3", expertise=("bus routes",))])
    result = s.match_executors("I01", scope="lineage")
    assert ids(result) == ["P01", "P02"]                   # P02 is the fleet manager in the parent node N4
    assert "P50" not in ids(s.match_executors("I01", scope="lineage", include_unmatched=True))
    assert result.matches[1].component("same_node").share == 0


def test_a_bad_scope_limit_or_issue_fails_without_raising(repos):
    s = make(repos)
    assert s.match_executors("I01", scope="world").outcome == FAILED
    assert s.match_executors("I01", limit=0).outcome == FAILED
    assert s.match_executors("I99").outcome == FAILED
    assert len(s.match_executors("I01", scope="lineage", limit=1).matches) == 1


def test_a_registered_executor_needs_a_known_node(repos):
    s = make(repos)
    refused = s.register_executor(executor("P90", node="N42"))
    assert refused.outcome == FAILED and "N42" in refused.detail
    assert s.register_executor(executor("P90", node="N6")).ok
    assert s.register_executor(executor("P90", node="N6")).outcome == FAILED       # same id again


def test_importing_the_seed_twice_adds_nothing_the_second_time(repos):
    s = make(repos, executors=[])
    first = s.import_seed(people())
    second = s.import_seed(people())
    assert len(first.executor_ids) == 6 and second.executor_ids == ()
    assert [str(e.executor_id) for e in s.executors.all_executors()] == ["P01", "P02", "P03", "P04", "P05", "P06"]


def test_the_import_refuses_an_executor_of_an_unknown_node(repos):
    s = make(repos, executors=[])
    result = s.import_seed([executor("P90", node="N42")])
    assert result.outcome == FAILED and s.executors.is_empty()


# --- mapping an executor to an issue feeds the progress factor -------------------------------------------------
def test_mapping_an_executor_raises_the_progress_by_the_executor_weight(repos):
    s = make(repos)
    before = compute_progress(s.issues.get("I04"), [], progress_weights()).value
    assert s.map_executor("I04", "P04").outcome == MAPPED
    after = compute_progress(s.issues.get("I04"), [], progress_weights()).value
    assert after - before == progress_weights().weight("executor_mapped") == 10
    assert [str(e.executor_id) for e in s.executors_of_issue("I04")] == ["P04"]


def test_the_executor_mapped_factor_is_the_one_that_moves(repos):
    s = make(repos)
    assert progress_factors(s.issues.get("I01"), [])["executor_mapped"] == 0
    s.map_executor("I01", "P01")
    assert progress_factors(s.issues.get("I01"), [])["executor_mapped"] == 1


def test_a_second_mapping_of_the_same_executor_is_refused_and_unmapping_works(repos):
    s = make(repos)
    assert s.map_executor("I01", "P01").ok
    assert s.map_executor("I01", "P01").outcome == FAILED
    assert s.map_executor("I01", "P03").ok
    assert s.issues.get("I01").executor_ids == ("P01", "P03")
    assert s.unmap_executor("I01", "P01").ok
    assert s.issues.get("I01").executor_ids == ("P03",)
    assert s.unmap_executor("I01", "P01").outcome == FAILED


def test_an_executor_from_another_branch_or_an_unknown_one_cannot_be_mapped(repos):
    s = make(repos)
    assert s.map_executor("I01", "P05").outcome == FAILED       # water engineer in N2
    assert s.map_executor("I01", "P99").outcome == FAILED
    assert s.map_executor("I99", "P01").outcome == FAILED
    assert s.map_executor("I01", "P02").ok                     # the parent node N4 is in the lineage
    assert s.issues.get("I01").executor_ids == ("P02",)


def test_without_a_hierarchy_mapping_stays_in_the_issues_node(repos):
    s = make(repos, with_hierarchy=False)
    assert s.map_executor("I01", "P02").outcome == FAILED
    assert s.map_executor("I01", "P01").ok
    assert s.match_executors("I01", scope="lineage").outcome == FAILED


def test_matching_does_not_change_the_issues(repos):
    s = make(repos)
    s.match_executors("I01", scope="lineage")
    assert s.issues.all_issues() == seed_issues()


def test_every_seed_issue_gets_a_deterministic_answer(repos):
    s = make(repos)
    for seed in seed_issues():
        a = s.match_executors(str(seed.issue_id), scope="lineage")
        b = s.match_executors(str(seed.issue_id), scope="lineage")
        assert a.ok and a.executor_ids == b.executor_ids
