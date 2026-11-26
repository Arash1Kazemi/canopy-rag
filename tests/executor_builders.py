"""Builders for the Phase 9 executor tests: the seed people, the match weights, and a service over any repositories."""
from issue_builders import city_hierarchy, city_nodes, seed_issues
from rag_core.executors.model import Executor
from rag_core.infrastructure.executors_csv import load_match_weights, seed_executors
from rag_core.infrastructure.memory import InMemoryExecutorRepository, InMemoryIssueRepository
from rag_core.workflows.executors import ExecutorService


def weights():
    return load_match_weights()


def people():
    return seed_executors(city_nodes())


def executor(executor_id="P90", node="N6", name="Test Person", expertise=("bus routes",), **fields):
    return Executor(executor_id=executor_id, name=name, node_id=node, expertise=expertise, **fields)


def service(executors=None, issues=None, executor_repo=None, issue_repo=None, with_hierarchy=True):
    """An ExecutorService with the seed people and the seed issues unless other lists are given."""
    executor_repo = executor_repo if executor_repo is not None else InMemoryExecutorRepository()
    issue_repo = issue_repo if issue_repo is not None else InMemoryIssueRepository()
    executor_repo.add_all(people() if executors is None else executors)
    issue_repo.add_all(seed_issues() if issues is None else issues)
    hierarchy = city_hierarchy() if with_hierarchy else None
    return ExecutorService(executor_repo, issue_repo, city_nodes(), weights(), (lambda: hierarchy) if hierarchy else None)
