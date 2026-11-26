"""The executor and IKE commands of `python -m rag_core` (Phase 9). __main__.py adds them with add_executor_commands.
None of them needs a model.

    python -m rag_core list-executors [--node N6]                       the executors (all, or one node)
    python -m rag_core match-executors --issue I01 [--scope node|lineage] [--limit 5]     ranked, with the reasons
    python -m rag_core map-executor --issue I01 --executor P01          save the mapping on the issue
    python -m rag_core ike-seed                                         load case_study/ike_seed_relations.csv (idempotent)
    python -m rag_core ike-summary --node N6 [--csv-out FILE] [--edges-out FILE]     the relation summary of a node

All take --db (default data/project.sqlite or RAG_DATA_DB). The people of case_study/people.csv become executors the first
time any of these commands runs (a second run adds nothing). Exit codes: 0 done, 1 a rule refused the change, 2 a setup
problem (unknown node, issue or executor, or a database without a hierarchy).
"""
import sys
from contextlib import ExitStack
from pathlib import Path

from .cli_issues import open_service
from .infrastructure.executors_csv import load_match_weights, seed_executors
from .infrastructure.project_db import migrate
from .infrastructure.sqlite_executors import SqliteExecutorRepository
from .infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from .infrastructure.sqlite_ike import SqliteIkeRepository
from .shared.kernel import DomainError
from .workflows.executors import SCOPES, ExecutorService
from .workflows.ike import IkeService, load_case_study


def _db(args):
    return Path(args.db) if args.db else migrate()


def _close_later(stack, thing):
    stack.callback(thing.close)
    return thing


def open_executors(args, stack):
    """The ExecutorService on one database file, with the seed people imported once. None (and a message) if not possible."""
    issues = open_service(args, stack)
    if issues is None:
        return None
    db = _db(args)
    executors = _close_later(stack, SqliteExecutorRepository(db))
    hierarchy = _close_later(stack, SqliteHierarchyRepository(db))
    service = ExecutorService(executors, issues.repo, issues.nodes, load_match_weights(), hierarchy=hierarchy.load)
    seeded = service.import_seed(seed_executors(issues.nodes))
    if not seeded.ok:
        raise DomainError(seeded.detail)
    return service


def run(args, action):
    with ExitStack() as stack:
        try:
            service = open_executors(args, stack)
        except (DomainError, ValueError) as error:
            print(f"failed: {error}", file=sys.stderr)
            return 2
        if service is None:
            return 2
        try:
            return action(service)
        except DomainError as error:        # an unknown node, issue or executor
            print(f"failed: {error}", file=sys.stderr)
            return 2


def cmd_list_executors(args):
    def action(service):
        found = service.executors_of_node(args.node) if args.node else service.executors.all_executors()
        if not found:
            print("no executors" + (f" in {args.node}" if args.node else ""))
            return 0
        for e in found:
            print(f"{e.executor_id}  {e.name}  ({e.node_id}, {e.role or 'no role'})  expertise: {'; '.join(e.expertise) or 'none'}")
            if e.documents_written:
                print(f"      wrote: {', '.join(f'{d.doc_id} {d.title}' for d in e.documents_written)}")
        return 0
    return run(args, action)


def cmd_match_executors(args):
    def action(service):
        service._require_issue(args.issue)
        result = service.match_executors(args.issue, scope=args.scope, limit=args.limit)
        if not result.ok:
            print(f"failed: {result.detail}", file=sys.stderr)
            return 1
        print(f"{result.detail}; the weights are untuned (config/executor_match_weights.csv), the list is for a person to read")
        for rank, match in enumerate(result.matches, 1):
            print(f"{rank}. " + "\n   ".join(match.explain()))
        if not result.matches:
            print("no executor has a matching expertise tag or document")
        return 0
    return run(args, action)


def cmd_map_executor(args):
    def action(service):
        service._require_issue(args.issue)
        service._require_executor(args.executor)
        result = service.map_executor(args.issue, args.executor)
        print(f"{result.outcome}: {result.detail}", file=sys.stdout if result.ok else sys.stderr)
        return 0 if result.ok else 1
    return run(args, action)


def run_ike(args, action):
    with ExitStack() as stack:
        try:
            issues = open_service(args, stack)
            if issues is None:
                return 2
            case = load_case_study()
            repo = _close_later(stack, SqliteIkeRepository(_db(args)))
            service = IkeService(repo, issues.nodes, issues.clock, **case.lookups)
            return action(service, case)
        except (DomainError, ValueError) as error:
            print(f"failed: {error}", file=sys.stderr)
            return 2


def cmd_ike_seed(args):
    def action(service, case):
        result = service.seed(case.seed_rows)
        print(f"{result.outcome}: {result.detail}", file=sys.stdout if result.ok else sys.stderr)
        return 0 if result.ok else 1
    return run_ike(args, action)


def cmd_ike_summary(args):
    def action(service, case):
        summary = service.summary(args.node, names=case.names)
        print(summary.to_text(), end="")
        for option, text in ((args.csv_out, summary.counts_csv()), (args.edges_out, summary.edges_csv())):
            if option:
                out = Path(option)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8", newline="")
                print(f"written: {out}")
        if not summary.total:
            print("note: no relations stored for this node (run ike-seed first)", file=sys.stderr)
        return 0
    return run_ike(args, action)


def add_executor_commands(sub):
    def db_option(p):
        p.add_argument("--db", help="database file (default data/project.sqlite or RAG_DATA_DB)")

    p = sub.add_parser("list-executors", help="the executors, all or one node's (Phase 9)")
    db_option(p)
    p.add_argument("--node")
    p.set_defaults(run=cmd_list_executors)

    p = sub.add_parser("match-executors", help="rank executors for an issue, with the reasons for each score")
    db_option(p)
    p.add_argument("--issue", required=True)
    p.add_argument("--scope", default="node", choices=SCOPES,
                   help="node: the issue's node only; lineage: also its ancestors and descendants")
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(run=cmd_match_executors)

    p = sub.add_parser("map-executor", help="map an executor to an issue (saved on the issue)")
    db_option(p)
    p.add_argument("--issue", required=True)
    p.add_argument("--executor", required=True)
    p.set_defaults(run=cmd_map_executor)

    p = sub.add_parser("ike-seed", help="load the seed IKE relations of the case study (a second run adds nothing)")
    db_option(p)
    p.set_defaults(run=cmd_ike_seed)

    p = sub.add_parser("ike-summary", help="the relation summary of a node (13.3)")
    db_option(p)
    p.add_argument("--node", required=True)
    p.add_argument("--csv-out", help="also write the counts by relation type to this CSV")
    p.add_argument("--edges-out", help="also write every relation to this CSV")
    p.set_defaults(run=cmd_ike_summary)
