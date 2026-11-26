"""The issue commands of `python -m rag_core` (Phase 7). __main__.py adds them with add_issue_commands.

    python -m rag_core list-issues --node N6                   the issues of a node, as a tree in sibling order
    python -m rag_core show-issue --id I01                     one issue: metadata, progress (H07), relative position
    python -m rag_core create-issue --node N6 --title "..." --description "..." [--parent I01] [--priority high]
                       [--category ...] [--type problem] [--blocked-by I02,I03] [--meta key=value ...]
    python -m rag_core set-issue-status --id I04 --status analyzing
    python -m rag_core compare-issue --node N6 --title "..." [--description "..."] [--top 5]
    python -m rag_core suggest-sub-issues --issue I01 [--model phi4-mini:3.8b] [--out FILE]     needs Ollama on 127.0.0.1:11500
    python -m rag_core accept-sub-issues --issue I01 --from FILE --take 1,3     save the chosen rows of a suggestions file

All take --db (default data/project.sqlite). The seed issues of case_study/issues.csv are imported the first time.
Measuring M15 (prepared, not run): suggest-sub-issues --issue I01 --out results/issues/m15_I01_suggestions.csv, then
a person fills the column matches_known_sub_issue with I02, I03, I04 or none.
"""
import csv
import datetime as dt
import sys
from contextlib import ExitStack
from pathlib import Path

from .infrastructure.issues_csv import SEED_FILE, SEED_SOURCE, issues_from_rows, load_progress_weights, read_rows
from .infrastructure.project_db import migrate
from .infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from .infrastructure.sqlite_issues import SqliteIssueRepository
from .issues.model import ISSUE_TYPES, PRIORITIES
from .issues.progress import progress_factors
from .issues.rules import check_issues, sibling_order
from .issues.status import IssueStatus
from .issues.suggestions import SubIssueSuggestion
from .organization.directory import RepositoryNodeDirectory
from .shared.kernel import DomainError
from .workflows.issues import IssueService

PROJECT = Path(__file__).resolve().parent.parent
PROMPT_FILE = PROJECT / "prompts" / "suggest_sub_issues_v1.txt"
PROMPT_ID = "P12"
SUGGESTION_COLUMNS = ["issue_id", "model", "prompt", "run_at", "number", "title", "description", "matches_known_sub_issue"]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_language_model(model_tag):
    """The real model. Tests replace this function with one that returns a stub."""
    from .infrastructure.ollama_language import OllamaLanguageModel
    return OllamaLanguageModel(model_tag)


def open_service(args, stack, clock=utc_now):
    """The IssueService on one database file, with the seed issues imported once. None (and a message) if not possible."""
    db = Path(args.db) if args.db else migrate()
    hierarchy = stack.enter_context(_closing(SqliteHierarchyRepository(db)))
    if hierarchy.is_empty():
        print(f"no hierarchy in {db}: run `python -m rag_core migrate-db --db {db}` first", file=sys.stderr)
        return None
    nodes = RepositoryNodeDirectory(hierarchy)
    repo = stack.enter_context(_closing(SqliteIssueRepository(db)))
    if not repo.was_imported(SEED_SOURCE):
        rows = repo.seed_rows()
        seed = issues_from_rows(rows if rows is not None else read_rows(SEED_FILE), clock(), nodes)
        check_issues(seed, repo.all_issues(), nodes)
        repo.import_once(SEED_SOURCE, seed, clock())
    return IssueService(repo, nodes, clock, load_progress_weights())


class _closing:
    def __init__(self, thing):
        self.thing = thing

    def __enter__(self):
        return self.thing

    def __exit__(self, *exc):
        self.thing.close()


def run(args, action):
    with ExitStack() as stack:
        try:
            service = open_service(args, stack)
        except (DomainError, ValueError) as error:
            print(f"failed: {error}", file=sys.stderr)
            return 2
        if service is None:
            return 2
        try:
            return action(service)
        except DomainError as error:
            print(f"failed: {error}", file=sys.stderr)
            return 1


def report(result):
    print(f"{result.outcome}: {result.detail}")
    return 0 if result.ok else 1


def split_list(text):
    return [x.strip() for x in (text or "").split(",") if x.strip()]


def cmd_create_issue(args):
    def action(service):
        node = args.node
        if node is None:
            if not args.parent or service.repo.get(args.parent) is None:
                print("failed: give --node, or a --parent that exists", file=sys.stderr)
                return 1
            node = str(service.repo.get(args.parent).node_id)
        metadata = {}
        for pair in args.meta or []:
            key, sep, value = pair.partition("=")
            if not sep:
                print(f"failed: --meta takes key=value, not {pair!r}", file=sys.stderr)
                return 1
            metadata[key.strip()] = value.strip()
        return report(service.create_issue(
            node, args.title, args.description, parent_id=args.parent, issue_type=args.type, priority=args.priority,
            category=args.category or "", field_of_activity=args.field, metadata=metadata,
            blocked_by=split_list(args.blocked_by)))
    return run(args, action)


def cmd_set_issue_status(args):
    return run(args, lambda service: report(service.set_status(args.id, args.status)))


def cmd_show_issue(args):
    def action(service):
        issue = service._require(args.id)
        progress = service.progress(issue.issue_id)
        where = service.position(issue.issue_id)
        ids = lambda xs: ", ".join(str(x) for x in xs) or "none"
        print(f"{issue.issue_id}  {issue.title}")
        print(f"  description:       {issue.description}")
        print(f"  node:              {issue.node_id}   field of activity: {issue.field_of_activity}")
        print(f"  status:            {issue.status.value}   type: {issue.issue_type}   priority: {issue.priority}"
              f"   category: {issue.category or 'none'}")
        print(f"  created:           {issue.created_at}")
        print(f"  metadata:          {'; '.join(f'{k}={v}' for k, v in issue.metadata) or 'none'}")
        print(f"  progress (H07):    {progress}")
        for name, share in progress_factors(issue, service.sub_issues(issue.issue_id)).items():
            print(f"      {name:<22} {float(share):.2f} x weight {service.weights.weight(name)}")
        print(f"  parent:            {where.parent_id or 'none'}   position among siblings: {where.position}")
        print(f"  siblings:          {ids(where.siblings)}")
        print(f"  sub-issues:        {ids(where.children)}")
        print(f"  blocked by:        {ids(where.blocked_by)}   blocks: {ids(where.blocks)}")
        print(f"  same category:     {ids(where.same_category)}")
        return 0
    return run(args, action)


def cmd_list_issues(args):
    def action(service):
        issues = service.issues_of_node(args.node)
        if not issues:
            print(f"no issues in {args.node}")
            return 0

        def show(parent, depth):
            for issue in sibling_order(i for i in issues if i.parent_issue_id == parent):
                print(f"{'  ' * depth}{issue.position}. {issue.issue_id} [{issue.status.value}, {service.progress(issue.issue_id)}] {issue.title}")
                show(issue.issue_id, depth + 1)
        show(None, 0)
        return 0
    return run(args, action)


def cmd_compare_issue(args):
    def action(service):
        result = service.compare(args.node, args.title, args.description or "")
        if not result.ok:
            return report(result)
        print(f"{result.detail} (same node only, stopwords removed, no threshold: decision A34)")
        for rank, m in enumerate(result.matches[: args.top], 1):
            print(f"{rank}. {m.issue_id}  score {m.score:.3f}  shared: {', '.join(m.shared_words)}  ({m.title})")
        return 0
    return run(args, action)


def cmd_suggest_sub_issues(args):
    def action(service):
        model = make_language_model(args.model)
        result = service.suggest_sub_issues(args.issue, model, PROMPT_FILE.read_text(encoding="utf-8"))
        if not result.ok:
            print(f"failed: {result.detail}", file=sys.stderr)
            return 2
        for n, s in enumerate(result.suggestions, 1):
            print(f"{n}. {s.title} | {s.description}")
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, SUGGESTION_COLUMNS, lineterminator="\n")
                writer.writeheader()
                run_at = utc_now()
                for n, s in enumerate(result.suggestions, 1):
                    writer.writerow({"issue_id": args.issue, "model": args.model, "prompt": f"{PROMPT_ID} {PROMPT_FILE.name}",
                                     "run_at": run_at, "number": n, "title": s.title, "description": s.description,
                                     "matches_known_sub_issue": ""})
            print(f"written: {out}")
        print("nothing is saved as an issue: accept the ones you want with accept-sub-issues")
        return 0
    return run(args, action)


def cmd_accept_sub_issues(args):
    def action(service):
        rows = {r["number"]: r for r in read_rows(args.source) if r["issue_id"] == args.issue}
        wanted = split_list(args.take)
        missing = [n for n in wanted if n not in rows]
        if not wanted or missing:
            print(f"failed: rows {', '.join(missing) or '(none given)'} are not suggestions for {args.issue} in {args.source}", file=sys.stderr)
            return 1
        chosen = [SubIssueSuggestion(rows[n]["title"], rows[n]["description"]) for n in wanted]
        return report(service.accept_sub_issues(args.issue, chosen))
    return run(args, action)


def add_issue_commands(sub):
    def db_option(p):
        p.add_argument("--db", help="database file (default data/project.sqlite or RAG_DATA_DB)")

    p = sub.add_parser("create-issue", help="create an issue or a sub-issue with its metadata (Phase 7)")
    db_option(p)
    p.add_argument("--node", help="the node; a sub-issue may leave it out and gets its parent's node")
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--parent", help="make it a sub-issue of this issue")
    p.add_argument("--type", default="problem", choices=ISSUE_TYPES)
    p.add_argument("--priority", default="not_set", choices=PRIORITIES)
    p.add_argument("--category", help="the issue's category inside its node")
    p.add_argument("--field", help="field of activity (default: the node's)")
    p.add_argument("--blocked-by", help="issues it waits on, such as I02,I03")
    p.add_argument("--meta", action="append", help="free metadata, key=value; repeat for more")
    p.set_defaults(run=cmd_create_issue)

    p = sub.add_parser("show-issue", help="one issue: metadata, progress and relative position")
    db_option(p)
    p.add_argument("--id", required=True)
    p.set_defaults(run=cmd_show_issue)

    p = sub.add_parser("list-issues", help="the issues of a node, as a tree in sibling order")
    db_option(p)
    p.add_argument("--node", required=True)
    p.set_defaults(run=cmd_list_issues)

    p = sub.add_parser("set-issue-status", help="move an issue to another status (only the allowed moves, H07)")
    db_option(p)
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=[s.value for s in IssueStatus])
    p.set_defaults(run=cmd_set_issue_status)

    p = sub.add_parser("compare-issue", help="rank the issues of the same node that resemble a draft")
    db_option(p)
    p.add_argument("--node", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description")
    p.add_argument("--top", type=int, default=5)
    p.set_defaults(run=cmd_compare_issue)

    p = sub.add_parser("suggest-sub-issues", help="ask the local LLM for sub-issues (needs Ollama on 127.0.0.1:11500)")
    db_option(p)
    p.add_argument("--issue", required=True)
    p.add_argument("--model", default="phi4-mini:3.8b", help="Ollama tag of the LLM (default: the baseline phi4-mini)")
    p.add_argument("--out", help="also write the suggestions to this CSV (for M15 and for accept-sub-issues)")
    p.set_defaults(run=cmd_suggest_sub_issues)

    p = sub.add_parser("accept-sub-issues", help="save chosen suggestions as sub-issues, all in one transaction")
    db_option(p)
    p.add_argument("--issue", required=True)
    p.add_argument("--from", dest="source", required=True, help="a CSV written by suggest-sub-issues --out (edit titles there)")
    p.add_argument("--take", required=True, help="the numbers of the rows to accept, such as 1,3; the others are rejected")
    p.set_defaults(run=cmd_accept_sub_issues)
