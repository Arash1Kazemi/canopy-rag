"""Command line for the core. Run from UNI-Project/:

    python -m rag_core extractors                       which formats can be read on this laptop
    python -m rag_core ingest-case-study                 ingest the 22 case-study files (the real DOCX and PDF files where the
                                                         manifest names one; --markdown for the Markdown only; --ocr for D19)
    python -m rag_core ingest-file PATH --item D19 --node N6 --version 2 --title "Meeting Minutes 18 June 2025"
    python -m rag_core make-samples                      DOCX and PDF copies of some case-study files, to test ingestion
    python -m rag_core find-duplicates --db results/ingestion/RUN/knowledge.sqlite    exact, near and overlap findings

    python -m rag_core migrate-db [--db FILE]           import the project datasets into SQLite
    python -m rag_core show-hierarchy [--db FILE]       show layers, nodes and transfer rules from SQLite
    python -m rag_core init-hierarchy [--db FILE]       initialize a hierarchy database
    python -m rag_core define-node --id N7 --name "..." --parent N4 --field "..."      add a node under a parent
    python -m rag_core move-node --id N6 --parent N5     give a node (and everything under it) a new parent
    python -m rag_core set-terminal --id N6 --knowledge-db FILE [--off]     make a node a black box, or open it again

    python -m rag_core list-issues --node N6 | show-issue --id I01 | create-issue ... | set-issue-status ...
    python -m rag_core compare-issue --node N6 --title "..." | suggest-sub-issues --issue I01 | accept-sub-issues ...
                                                         the issue commands (Phase 7), details in rag_core/cli_issues.py

    python -m rag_core list-executors [--node N6] | match-executors --issue I01 [--scope node|lineage] [--limit 5]
    python -m rag_core map-executor --issue I01 --executor P01 | ike-seed | ike-summary --node N6 [--csv-out F] [--edges-out F]
                                                         executors and IKE (Phase 9, no model), details in rag_core/cli_executors.py

    python -m rag_core index [--db FILE] [--fake-models]            embed and index the case study (Phase 8)
    python -m rag_core ask --node N6 "question" [--prompt P01|P13] [--k 3] [--db FILE]     answer with checked citations
    python -m rag_core evaluate [--run-id ID] [--prompt P01|P13] [--fake-models]     the 26 questions through the core,
                                                         graded like the baseline and compared with results/e3-first
                                                         (details in rag_core/cli_rag.py; exit code 2 if Ollama is unreachable)

ingest-case-study and ingest-file take --detect-duplicates: near duplicates and overlaps become notes in the report
and a duplicates.csv is written next to the database.
"""
import argparse
import datetime as dt
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

from .infrastructure import csv_export
from .infrastructure.project_db import database_path, migrate, project_rows
from .infrastructure.registry_csv import hierarchy_from_rows
from .infrastructure.sqlite import SqliteKnowledgeRepository
from .infrastructure.sqlite_hierarchy import SqliteHierarchyRepository
from .ingestion.case_study import manifest_requests
from .ingestion.extractors import Extractors
from .ingestion.samples import markdown_to_docx, text_to_pdf
from .ingestion.service import FAILED, IngestionService, RegistrationRequest
from .knowledge.chunking import DEFAULT_POLICY, POLICIES
from .knowledge.duplicates import DuplicateDetector
from .workflows.organization import OrganizationService

PROJECT = Path(__file__).resolve().parent.parent
CASE = PROJECT / "case_study"
REGISTRY = PROJECT / "registry" / "node_layer_registry.csv"
RESULTS = PROJECT / "results" / "ingestion"
LAYER_REGISTRY = PROJECT / "registry" / "layer_registry.csv"
SAMPLE_DOCS = ("D10_bus_fleet_inventory_v2", "D13_maintenance_schedule_2025", "D17_pilot_test_report",
               "D19_meeting_minutes_2025-06-18", "D20_cost_estimate")


def make_extractors(args):
    vision = None
    if getattr(args, "ocr", False):
        from .infrastructure.ollama_models import OllamaVisionModel
        vision = OllamaVisionModel(args.lvm) if args.lvm else OllamaVisionModel()
    return Extractors(vision=vision)


def print_results(results):
    for r in results:
        line = f"{r.outcome:<22} {r.request.item_id:<5} v{r.request.version_tag:<3} {Path(r.request.path).name:<42} {r.chunks:>3} chunks"
        print(line + (f"  ({r.detail})" if r.detail else ""))
        for w in r.warnings:
            print(f"{'':<22} note: {w}")
    counts = Counter(r.outcome for r in results)
    print("\n" + ", ".join(f"{n} {k}" for k, n in counts.items()))


def cmd_extractors(args):
    for label, name, state in make_extractors(args).status():
        print(f"{label:<12} {name:<22} {state}")


def run_ingest(args, requests, out):
    database = migrate()
    if args.hierarchy_db:
        database = Path(args.hierarchy_db)
        if not database.is_file():
            print(f"no hierarchy database at {database}", file=sys.stderr)
            return 2
    with closing(SqliteHierarchyRepository(database)) as hierarchy_repo:
        hierarchy = hierarchy_repo.load()
    knowledge_db = out / "knowledge.sqlite" if args.out or getattr(args, "run_id", None) else database_path()
    repo = SqliteKnowledgeRepository(knowledge_db)
    detector = DuplicateDetector() if args.detect_duplicates else None
    service = IngestionService(hierarchy, repo, make_extractors(args), policy=args.policy, detector=detector)
    results = [service.register(r) for r in requests]
    csv_export.export(repo, out)
    if detector is not None:
        csv_export.write_rows(out / "duplicates.csv", csv_export.DUPLICATE_COLUMNS,
                              csv_export.duplicate_rows(detector.scan(repo.all_items())))
    csv_export.write_rows(out / "ingestion_report.csv", csv_export.REPORT_COLUMNS, [
        {"source_file": Path(r.request.path).name, "item_id": r.request.item_id, "version_tag": r.request.version_tag,
         "node_id": r.request.node_id, "outcome": r.outcome, "chunks": r.chunks,
         "detail": "; ".join(x for x in (r.detail, *r.warnings) if x)} for r in results])
    repo.close()
    print_results(results)
    print(f"written: {out}")
    return 1 if any(r.outcome == FAILED for r in results) else 0


def out_folder(args):
    run_id = getattr(args, "run_id", None)
    return Path(args.out) if args.out else RESULTS / (run_id or dt.datetime.now().strftime("%Y%m%d-%H%M%S"))


def cmd_ingest_case_study(args):
    rows = project_rows(CASE / "documents_manifest.csv")
    if not args.markdown and rows and "real_file" not in rows[0]:
        print("note: the manifest in the project database has no real_file column (it was copied there before the real "
              "DOCX and PDF files existed), so the Markdown files are read. To read the real files, point RAG_DATA_DB "
              "at a new database file.", file=sys.stderr)
    requests = manifest_requests(CASE, args.documents, args.suffix, read_rows=lambda _: rows,
                                 real_files=not args.markdown, lvm=args.ocr)
    return run_ingest(args, requests, out_folder(args))


def cmd_ingest_file(args):
    request = RegistrationRequest(Path(args.path), args.item, args.node, args.version, args.title,
                                  change_reason=args.reason or "")
    return run_ingest(args, [request], out_folder(args))


def cmd_find_duplicates(args):
    db = Path(args.db)
    if not db.exists():
        print(f"no database at {db}", file=sys.stderr)
        return 2
    repo = SqliteKnowledgeRepository(db)
    records = DuplicateDetector().scan(repo.all_items(), all_versions=args.all_versions)
    repo.close()
    out = Path(args.out) if args.out else db.parent / "duplicates.csv"
    csv_export.write_rows(out, csv_export.DUPLICATE_COLUMNS, csv_export.duplicate_rows(records))
    for r in records:
        print(f"{r.kind.value:<8} {r.left_item} v{r.left_tag}  <->  {r.right_item} v{r.right_tag}   {r.evidence}")
    print(f"{len(records)} finding(s) among {'all versions' if args.all_versions else 'active versions'}; written: {out}")
    return 0


def print_hierarchy(h):
    for layer in h.layers():
        rule = layer.rule
        receives = (f"receives {rule.detail_level.value} packages, minimum judge score {rule.min_judge_score or 'not set'}"
                    if rule else "receives nothing")
        print(f"Layer {layer.index.value}: {layer.name or '(not in the layer registry)'}  [{receives}]")
        if layer.role:
            print(f"    role: {layer.role}")
        if rule:
            if rule.required_topics:
                print(f"    required topics: {'; '.join(rule.required_topics)}")
            unset = [name for name, value in (("excluded topics", rule.excluded_topics), ("required fields", rule.required_fields),
                                              ("output format", rule.output_format), ("maximum length", rule.max_words),
                                              ("citation level", rule.citation_level)) if not value]
            if unset:
                print(f"    not decided yet: {', '.join(unset)}")
    print("\nNodes:")

    def show(node, depth):
        sends = f"sends {node.reporting_format.value}, judge >= {node.min_judge_score}" if node.reporting_format else "sends nothing up"
        print(f"{'  ' * depth}{node.node_id} {node.name} ({node.field_of_activity}), layer {node.layer.value}"
              f"{' [terminal]' if node.is_terminal else ''}: {sends}")
        for child in h.children(node.node_id):
            show(child, depth + 1)
    show(h.root(), 0)
    problems = h.problems()
    print("\nProblems: " + ("none" if not problems else "\n  " + "\n  ".join(problems)))


def hierarchy_repository(args, must_have_data=True):
    repo = SqliteHierarchyRepository(Path(args.db) if args.db else migrate())
    if must_have_data and repo.is_empty():
        print("this hierarchy database is empty: run init-hierarchy first", file=sys.stderr)
        repo.close()
        return None
    return repo


def cmd_show_hierarchy(args):
    repo = hierarchy_repository(args)
    if repo is None:
        return 2
    with closing(repo):
        hierarchy = repo.load()
    print_hierarchy(hierarchy)
    return 0


def cmd_init_hierarchy(args):
    if not args.db:
        return cmd_migrate_db(args)
    repo = hierarchy_repository(args, must_have_data=False)
    if not repo.is_empty():
        print("this hierarchy database already has nodes; delete the file to start again", file=sys.stderr)
        repo.close()
        return 2
    repo.save(hierarchy_from_rows(project_rows(REGISTRY), project_rows(LAYER_REGISTRY)))
    repo.close()
    print(f"hierarchy database written: {args.db}")
    return 0


def cmd_migrate_db(args):
    print(f"project database ready: {migrate(args.db)}")
    return 0


def run_workflow(args, action, knowledge_db=None):
    repo = hierarchy_repository(args)
    if repo is None:
        return 2
    knowledge = SqliteKnowledgeRepository(knowledge_db) if knowledge_db else None
    try:
        result = action(OrganizationService(repo, knowledge))
    finally:
        repo.close()
        if knowledge is not None:
            knowledge.close()
    print(f"{result.outcome}: {result.detail}")
    return 0 if result.ok else 1


def cmd_define_node(args):
    return run_workflow(args, lambda s: s.define_node(
        args.id, args.name, args.parent, args.field, is_terminal=args.terminal, confidentiality=args.confidentiality,
        reporting_format=args.reporting_format, min_judge_score=args.min_judge_score))


def cmd_move_node(args):
    return run_workflow(args, lambda s: s.move_node(args.id, args.parent))


def cmd_set_terminal(args):
    knowledge_db = args.knowledge_db or (migrate() if not args.db and not args.off else None)
    return run_workflow(args, lambda s: s.set_terminal(args.id, not args.off), knowledge_db=knowledge_db)


def cmd_make_samples(args):
    out = Path(args.out) if args.out else RESULTS / "samples"
    for row in manifest_requests(CASE, read_rows=project_rows):
        stem = Path(row.path).stem
        if stem in SAMPLE_DOCS:
            text = Path(row.path).read_text(encoding="utf-8")
            folder = out / Path(row.source_file).parent
            print(markdown_to_docx(text, folder / f"{stem}.docx"))
            print(text_to_pdf(text, folder / f"{stem}.pdf"))
    print("The real DOCX and PDF files, and D19 as an image-only PDF, are made by scripts/make_real_files.py")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m rag_core")
    sub = parser.add_subparsers(dest="command", required=True)

    def ocr_options(p):
        p.add_argument("--ocr", action="store_true", help="read image-only PDFs with the LVM through Ollama (127.0.0.1)")
        p.add_argument("--lvm", help="Ollama tag of the LVM (default glm-ocr:q8_0)")

    p = sub.add_parser("extractors", help="which formats can be read on this laptop")
    ocr_options(p)
    p.set_defaults(run=cmd_extractors)

    p = sub.add_parser("ingest-case-study", help="ingest the case-study files into SQLite")
    p.add_argument("--documents", help="read the files from this folder instead of case_study/documents")
    p.add_argument("--suffix", help="read converted copies with this suffix, such as .docx or .pdf")
    p.add_argument("--markdown", action="store_true",
                   help="read only the Markdown sources, not the real DOCX and PDF files the manifest names")
    p.add_argument("--policy", default=DEFAULT_POLICY, choices=sorted(POLICIES))
    p.add_argument("--detect-duplicates", action="store_true", help="note near duplicates and overlaps, write duplicates.csv")
    p.add_argument("--run-id", help="name of the results folder")
    p.add_argument("--out", help="the results folder (default results/ingestion/<run-id>)")
    p.add_argument("--hierarchy-db", help="use a separate hierarchy database")
    ocr_options(p)
    p.set_defaults(run=cmd_ingest_case_study)

    p = sub.add_parser("ingest-file", help="register one file as a new item or a new version")
    p.add_argument("path")
    p.add_argument("--item", required=True)
    p.add_argument("--node", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--reason", help="why this version was added")
    p.add_argument("--detect-duplicates", action="store_true", help="note near duplicates and overlaps, write duplicates.csv")
    p.add_argument("--policy", default=DEFAULT_POLICY, choices=sorted(POLICIES))
    p.add_argument("--out", help="the results folder that holds knowledge.sqlite")
    p.add_argument("--hierarchy-db", help="use a separate hierarchy database")
    ocr_options(p)
    p.set_defaults(run=cmd_ingest_file)

    p = sub.add_parser("find-duplicates", help="list exact, near and overlap findings in a knowledge database")
    p.add_argument("--db", required=True, help="the knowledge.sqlite to scan")
    p.add_argument("--all-versions", action="store_true", help="compare every version, not only the active ones")
    p.add_argument("--out", help="the CSV to write (default duplicates.csv next to the database)")
    p.set_defaults(run=cmd_find_duplicates)

    def db_option(p):
        p.add_argument("--db", help="database file (default data/project.sqlite or RAG_DATA_DB)")

    p = sub.add_parser("migrate-db", help="import the project CSV datasets into SQLite once")
    db_option(p)
    p.set_defaults(run=cmd_migrate_db)

    p = sub.add_parser("show-hierarchy", help="the layers, the nodes and the transfer rules")
    db_option(p)
    p.set_defaults(run=cmd_show_hierarchy)

    p = sub.add_parser("init-hierarchy", help="copy the registry CSVs into a hierarchy database")
    db_option(p)
    p.set_defaults(run=cmd_init_hierarchy)

    p = sub.add_parser("define-node", help="add a node under a parent; its layer is the parent's plus one")
    db_option(p)
    p.add_argument("--id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--parent", required=True)
    p.add_argument("--field", required=True, help="the node's field of activity")
    p.add_argument("--terminal", action="store_true")
    p.add_argument("--confidentiality", default="internal", choices=["internal", "confidential"])
    p.add_argument("--reporting-format", help="only when the parent's layer has no transfer rule")
    p.add_argument("--min-judge-score", type=int, help="only when the rule of the parent's layer sets none")
    p.set_defaults(run=cmd_define_node)

    p = sub.add_parser("move-node", help="give a node, and everything under it, a new parent")
    db_option(p)
    p.add_argument("--id", required=True)
    p.add_argument("--parent", required=True)
    p.set_defaults(run=cmd_move_node)

    p = sub.add_parser("set-terminal", help="make a node a terminal node (a black box), or open it again with --off")
    db_option(p)
    p.add_argument("--id", required=True)
    p.add_argument("--off", action="store_true", help="open the node again")
    p.add_argument("--knowledge-db", help="the knowledge.sqlite, to check that the node has at most one summary document")
    p.set_defaults(run=cmd_set_terminal)

    p = sub.add_parser("make-samples", help="DOCX and PDF copies of five case-study files")
    p.add_argument("--out")
    p.set_defaults(run=cmd_make_samples)

    from .cli_issues import add_issue_commands
    add_issue_commands(sub)
    from .cli_rag import add_rag_commands
    add_rag_commands(sub)
    from .cli_executors import add_executor_commands
    add_executor_commands(sub)

    args = parser.parse_args(argv)
    return args.run(args) or 0


if __name__ == "__main__":
    sys.exit(main())
