#!/usr/bin/env python3
"""Run the Phase 1 consistency checks.

    python tools/run_checks.py

Three validators, each reports PASS or FAIL:
  case_study          documents, manifest, answer key, issues, people
  registry            node and layer rules, and the links to the case study
  scope_and_glossary  objectives, proposal traceability, glossary, and the
                      Markdown pages and READMEs that repeat their numbers

Standard library only. Exit code 0 = everything passed, 1 = something failed.
"""
import csv
import hashlib
import itertools
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT
CASE = ROOT / "case_study"
DOCS = CASE / "documents"
REGISTRY = ROOT / "registry"
SCOPE = ROOT / "scope"
GLOSSARY = ROOT / "glossary"
METRICS = ROOT / "metrics"
GUIDES = ROOT / "docs"

# Facts about the frozen case study and the objectives. If you change one on
# purpose, change it here too: this is the tripwire for accidental edits.
EXPECTED = dict(
    nodes=7, layers=4, files=22, documents=20, questions=26,
    issues=7, sub_issues_of_I01=3, people=6, objectives=8, proposal_objectives=20,
    metrics=28, hard_rules=10, test_areas=14,
    real_files=5,  # Phase 4: DOCX and PDF files made from the Markdown by scripts/make_real_files.py
)

MANIFEST_COLUMNS = ["doc_id", "file", "node_id", "title", "language", "version", "planted_problem", "real_file", "real_format"]
# real_format -> the suffix of the real file. The Markdown in `file` stays the source of truth (and what the
# checks below read); the real file sits beside it with the same stem, so citations and the answer key do not change.
REAL_FORMATS = {"docx": ".docx", "pdf_text": ".pdf", "pdf_image_only": ".pdf"}
KEY_COLUMNS = ["question_id", "asked_at_node", "language", "type", "question", "expected_answer", "source_files"]
ISSUE_COLUMNS = ["issue_id", "node_id", "parent_issue_id", "title", "description", "status"]
PEOPLE_COLUMNS = ["person_id", "name", "node_id", "role", "expertise"]
REGISTRY_COLUMNS = [
    "node_id", "name", "layer_index", "parent_node_id", "field_of_activity",
    "is_terminal", "reporting_format", "min_judge_score", "confidentiality",
]
LAYER_COLUMNS = [
    "layer_index", "name", "role", "detail_level", "min_judge_score", "required_topics", "excluded_topics",
    "required_fields", "output_format", "max_words", "citation_level", "source",
]
CITATION_LEVELS = {"short", "long"}
OBJECTIVE_COLUMNS = [
    "objective_id", "title", "statement", "priority", "proposal_phases",
    "proposal_objectives", "answer_key_questions", "how_checked", "target",
]
TRACE_COLUMNS = ["proposal_objective", "summary", "project_objectives"]
GLOSSARY_COLUMNS = ["term", "area", "kind", "source", "context", "meaning", "avoid", "code_name"]
METRIC_COLUMNS = [
    "metric_id", "objective_id", "component", "name", "definition", "unit", "direction", "data",
    "grading_rules", "method", "first_measured_in_phase", "baseline", "baseline_source", "target", "target_source",
]
GRADING_COLUMNS = ["rule_id", "name", "rule", "automatic"]
TYPE_RULE_COLUMNS = ["question_type", "grading_rules"]
FACT_COLUMNS = ["question_id", "required", "forbidden"]
HARD_COLUMNS = ["rule_id", "objective_id", "statement", "how_tested"]
COMPONENTS = {"ingestion", "extraction", "retrieval", "answering", "issues", "transfer", "judge", "runtime", "engineering", "rfp"}
METHODS = {"automatic", "judge", "human", "mixed"}
# Until the supervisor agrees a target, this text stays. A number needs a target_source.
TARGET_PLACEHOLDER = "to agree with supervisor"

QUESTION_TYPES = {
    "version_trap", "duplicate", "factual", "contradiction", "scanned_pdf",
    "multi_document", "terminal_node", "node_boundary", "unanswerable", "version_history",
}
REFUSAL_TYPES = {"unanswerable", "node_boundary"}  # the system must say "insufficient knowledge"
# Detail gets coarser going up, so a child's format is at least as detailed as its parent's.
DETAIL_RANK = {"executive": 1, "managerial": 2, "technical_summary": 3, "detailed_technical": 4}
CONFIDENTIALITY = {"internal", "confidential"}
# The proposal's 10 bounded contexts, as used in the glossary.
CONTEXTS = {
    "Organizational Hierarchy", "Knowledge Management", "RAG Core", "Issue Management",
    "Executor Management", "Issue-Knowledge-Executor", "Knowledge Transfer",
    "Evaluation and Judging", "Model and Prompt Management", "RFP and Proposal Management",
}
CODE_NAME_PLACEHOLDER = "decided in Phase 3"
PERSIAN = re.compile(r"[؀-ۿ]")


class Abort(Exception):
    """Stop one validator early, for example when a file has the wrong columns."""


class Report:
    """Collects the results of one validator."""

    def __init__(self, name):
        self.name = name
        self.checks = 0
        self.problems = []

    def check(self, ok, message):
        self.checks += 1
        if not ok:
            self.problems.append(message)

    def fail(self, message):
        self.check(False, message)

    def load_csv(self, path, columns):
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header, rows = reader.fieldnames, list(reader)
        ok = header == columns
        self.check(ok, f"{path.relative_to(PROJECT)}: columns are {header}, expected {columns}")
        if not ok:
            raise Abort
        return rows


def hygiene(r, folder, skip=()):
    """CSV files: UTF-8, LF, no BOM. CSV and Markdown: English only. `skip` names folders to leave out."""
    for f in sorted(folder.rglob("*")):
        if f.suffix not in (".csv", ".md") or any(part in skip for part in f.relative_to(folder).parts):
            continue
        rel = f.relative_to(PROJECT)
        raw = f.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            r.fail(f"{rel}: not valid UTF-8")
            continue
        if f.suffix == ".csv":
            r.check(not raw.startswith(b"\xef\xbb\xbf"), f"{rel}: starts with a BOM")
            r.check(b"\r\n" not in raw, f"{rel}: has CRLF line endings, use LF")
        r.check(not PERSIAN.search(text), f"{rel}: contains Persian text (English only for now)")


def md_tables(text):
    """Yield (nearest heading, header cells, body rows) for each Markdown table."""
    heading, block = "", []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            block.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        if block:
            yield heading, block[0], block[2:]  # block[1] is the --- separator row
            block = []
        if line.startswith("#"):
            heading = line.lstrip("#").strip()


def split_ids(cell, sep=";"):
    return {part.strip() for part in cell.split(sep) if part.strip()}


def doc_text(manifest, doc_id, version=None):
    for row in manifest:
        if row["doc_id"] == doc_id and (version is None or row["version"] == version):
            return (DOCS / row["file"]).read_text(encoding="utf-8")
    raise Abort


# ---------------------------------------------------------------- validator 1
def check_case_study(r):
    hygiene(r, CASE)
    manifest = r.load_csv(CASE / "documents_manifest.csv", MANIFEST_COLUMNS)
    node_ids = {row["node_id"] for row in r.load_csv(REGISTRY / "node_layer_registry.csv", REGISTRY_COLUMNS)}

    # manifest <-> files on disk
    on_disk = {p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*") if p.is_file()}
    listed = [row["file"] for row in manifest]
    real = [row["real_file"] for row in manifest if row["real_file"]]
    r.check(len(listed) == len(set(listed)), "manifest lists the same file twice")
    for f in listed + real:
        r.check(f in on_disk, f"manifest lists a file that does not exist: {f}")
    for f in sorted(on_disk):
        r.check(f in listed or f in real, f"file is not in the manifest: {f}")
    r.check(all(f.endswith(".md") for f in listed), "the file column names the Markdown sources (.md)")

    # real files (Phase 4): beside their Markdown, same stem, and what real_format says
    r.check(len(real) == len(set(real)) == EXPECTED["real_files"],
            f"manifest names {len(real)} real files, expected {EXPECTED['real_files']} different ones")
    for row in manifest:
        name, fmt = row["real_file"], row["real_format"]
        r.check(bool(name) == bool(fmt), f"{row['file']}: real_file and real_format are both set or both empty")
        if not name:
            continue
        r.check(fmt in REAL_FORMATS, f"{name}: unknown real_format {fmt}; known: {', '.join(REAL_FORMATS)}")
        md, made = Path(row["file"]), Path(name)
        r.check(made.parent == md.parent and made.stem == md.stem, f"{name}: must sit beside {row['file']} with the same stem")
        r.check(made.suffix == REAL_FORMATS.get(fmt), f"{name}: a {fmt} file ends in {REAL_FORMATS.get(fmt)}")
        r.check(row["doc_id"] not in ("D10", "D12"), f"{name}: the version and duplicate traps (D10, D12) stay Markdown")
        path = DOCS / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if fmt == "docx":
            r.check(data.startswith(b"PK\x03\x04"), f"{name}: is not a DOCX (ZIP) file")
        else:
            r.check(data.startswith(b"%PDF-"), f"{name}: is not a PDF file")
            # a text PDF names a font; an image-only PDF (a scan) has no font, so it has no text layer
            r.check((b"/Font" in data) == (fmt == "pdf_text"), f"{name}: {fmt} {'needs' if fmt == 'pdf_text' else 'must not have'} a font")
    r.check([row["doc_id"] for row in manifest if row["real_format"] == "pdf_image_only"] == ["D19"],
            "D19, and only D19, is the image-only (scanned) PDF")
    r.check(len(manifest) == EXPECTED["files"], f"manifest has {len(manifest)} files, expected {EXPECTED['files']}")
    doc_ids = sorted({row["doc_id"] for row in manifest})
    want_ids = [f"D{i:02d}" for i in range(1, EXPECTED["documents"] + 1)]
    r.check(doc_ids == want_ids, f"document ids are {doc_ids}, expected D01 to D{EXPECTED['documents']:02d}")
    for row in manifest:
        name = row["file"]
        r.check(row["language"] == "en", f"{name}: language is {row['language']}, expected en")
        r.check(name.split("/")[-1].startswith(row["doc_id"] + "_"), f"{name}: file name does not start with {row['doc_id']}")
        r.check(name.split("_")[0] == row["node_id"], f"{name}: folder does not match node {row['node_id']}")
        r.check(row["node_id"] in node_ids, f"{name}: node {row['node_id']} is not in the registry")

    # same doc_id: same version means byte-identical (exact duplicate), different version means different content
    def digest(row):
        path = DOCS / row["file"]
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

    by_doc = defaultdict(list)
    for row in manifest:
        by_doc[row["doc_id"]].append(row)
    exact_pairs = version_pairs = 0
    for doc_id, rows in by_doc.items():
        for a, b in itertools.combinations(rows, 2):
            r.check(a["node_id"] == b["node_id"], f"{doc_id}: copies and versions must stay in one node")
            da, db = digest(a), digest(b)
            if da is None or db is None:
                continue
            if a["version"] == b["version"]:
                exact_pairs += 1
                r.check(da == db, f"{doc_id}: two files with version {a['version']} are not identical")
            else:
                version_pairs += 1
                r.check(da != db, f"{doc_id}: versions {a['version']} and {b['version']} are identical files")
    r.check(exact_pairs == 1, f"expected 1 exact-duplicate pair (D12), found {exact_pairs}")
    r.check(version_pairs == 1, f"expected 1 old-version pair (D10), found {version_pairs}")

    # answer key
    key = r.load_csv(CASE / "answer_key.csv", KEY_COLUMNS)
    r.check(len(key) == EXPECTED["questions"], f"answer key has {len(key)} questions, expected {EXPECTED['questions']}")
    r.check([q["question_id"] for q in key] == [f"Q{i:02d}" for i in range(1, len(key) + 1)],
            "question ids must run Q01, Q02, ... with no gaps or repeats")
    node_of_doc = {row["doc_id"]: row["node_id"] for row in manifest}
    for q in key:
        qid, asked = q["question_id"], q["asked_at_node"]
        refuse = q["type"] in REFUSAL_TYPES
        refs = re.findall(r"\bD\d\d", q["source_files"])
        r.check(q["language"] == "en", f"{qid}: language is {q['language']}, expected en")
        r.check(asked in node_ids, f"{qid}: asked at unknown node {asked}")
        r.check(q["type"] in QUESTION_TYPES, f"{qid}: unknown type {q['type']}")
        r.check(bool(q["question"].strip() and q["expected_answer"].strip()), f"{qid}: empty question or answer")
        r.check(refuse == q["source_files"].startswith("none"), f"{qid}: only unanswerable and node_boundary questions have source 'none'")
        r.check(refuse == q["expected_answer"].startswith("Insufficient knowledge"),
                f"{qid}: only unanswerable and node_boundary answers start with 'Insufficient knowledge'")
        r.check(bool(refs) != refuse, f"{qid}: needs at least one source document unless it is a refusal question")
        for d in refs:
            r.check(d in node_of_doc, f"{qid}: unknown document {d}")
            r.check(node_of_doc.get(d) == asked, f"{qid}: {d} lives in {node_of_doc.get(d)} but the question is asked at {asked}")

    # issues and people
    issues = r.load_csv(CASE / "issues.csv", ISSUE_COLUMNS)
    issue_node = {i["issue_id"]: i["node_id"] for i in issues}
    r.check(len(issue_node) == len(issues), "issue ids repeat")
    r.check(len(issues) == EXPECTED["issues"], f"{len(issues)} issues, expected {EXPECTED['issues']}")
    for i in issues:
        r.check(i["node_id"] in node_ids, f"{i['issue_id']}: unknown node {i['node_id']}")
        r.check(bool(i["status"].strip()), f"{i['issue_id']}: empty status")
        if i["parent_issue_id"]:
            r.check(i["parent_issue_id"] in issue_node, f"{i['issue_id']}: unknown parent {i['parent_issue_id']}")
            r.check(issue_node.get(i["parent_issue_id"]) == i["node_id"], f"{i['issue_id']}: a sub-issue stays in its parent's node")
    subs = [i for i in issues if i["parent_issue_id"] == "I01"]
    r.check(len(subs) == EXPECTED["sub_issues_of_I01"], f"I01 has {len(subs)} sub-issues, expected {EXPECTED['sub_issues_of_I01']}")
    people = r.load_csv(CASE / "people.csv", PEOPLE_COLUMNS)
    r.check(len({p["person_id"] for p in people}) == len(people), "person ids repeat")
    r.check(len(people) == EXPECTED["people"], f"{len(people)} people, expected {EXPECTED['people']}")
    for p in people:
        r.check(p["node_id"] in node_ids, f"{p['person_id']}: unknown node {p['node_id']}")

    # planted problems must still be planted
    v1, v2 = doc_text(manifest, "D10", "1"), doc_text(manifest, "D10", "2")
    r.check("120" in v1 and "135" not in v1, "D10 v1 must say 120 buses and not 135")
    r.check("135" in v2, "D10 v2 must say 135 buses")
    r.check("Route 12 is the busiest" in doc_text(manifest, "D11"), "D11 must say Route 12 is the busiest")
    r.check("Route 7" in doc_text(manifest, "D16"), "D16 must mention Route 7")
    boundary = [q for q in key if q["type"] == "node_boundary"]
    r.check(len(boundary) == 1, f"expected 1 node_boundary question, found {len(boundary)}")
    if boundary:
        asked = boundary[0]["asked_at_node"]
        own = [(DOCS / m["file"]).read_text(encoding="utf-8").lower() for m in manifest if m["node_id"] == asked]
        other = [(DOCS / m["file"]).read_text(encoding="utf-8").lower() for m in manifest if m["node_id"] != asked]
        r.check(not any("chlorine" in t for t in own), f"node {asked} must not have a document with the chlorine answer")
        r.check(any("chlorine" in t for t in other), "the chlorine answer must exist in another node")


# ---------------------------------------------------------------- validator 2
def check_registry(r):
    hygiene(r, REGISTRY)
    rows = r.load_csv(REGISTRY / "node_layer_registry.csv", REGISTRY_COLUMNS)
    manifest = r.load_csv(CASE / "documents_manifest.csv", MANIFEST_COLUMNS)

    readme = (REGISTRY / "README.md").read_text(encoding="utf-8")
    first_table = next((body for _, _, body in md_tables(readme)), [])
    r.check([cells[0] for cells in first_table] == REGISTRY_COLUMNS, "registry README documents different columns than the CSV has")

    by_id = {row["node_id"]: row for row in rows}
    r.check(len(by_id) == len(rows), "node_id repeats")
    r.check(len(rows) == EXPECTED["nodes"], f"{len(rows)} nodes, expected {EXPECTED['nodes']}")
    roots = [row for row in rows if not row["parent_node_id"]]
    r.check(len(roots) == 1, f"{len(roots)} root nodes, expected exactly 1")

    children = defaultdict(list)
    layers = set()
    for row in rows:
        n = row["node_id"]
        r.check(re.fullmatch(r"N\d+", n) is not None, f"{n}: node ids look like N0, N1, ...")
        r.check(row["layer_index"].isdigit(), f"{n}: layer_index must be a whole number")
        if not row["layer_index"].isdigit():
            continue
        layer, parent = int(row["layer_index"]), row["parent_node_id"]
        layers.add(layer)
        if parent:
            r.check(parent in by_id, f"{n}: parent {parent} is not in the registry")
            if parent in by_id and by_id[parent]["layer_index"].isdigit():
                r.check(layer == int(by_id[parent]["layer_index"]) + 1, f"{n}: layer must be its parent's layer + 1")
                children[parent].append(n)
        else:
            r.check(layer == 0, f"{n}: the root must be layer 0")
        r.check(bool(row["field_of_activity"].strip()), f"{n}: field_of_activity is empty")
        r.check(row["confidentiality"] in CONFIDENTIALITY, f"{n}: confidentiality must be internal or confidential")
        r.check(row["is_terminal"] in ("true", "false"), f"{n}: is_terminal must be true or false")

        fmt, score = row["reporting_format"], row["min_judge_score"]
        if not parent:
            r.check(fmt == "none" and score == "", f"{n}: the root sends nothing up, so reporting_format is none and min_judge_score is empty")
        else:
            r.check(fmt in DETAIL_RANK, f"{n}: unknown reporting_format {fmt}")
            r.check(score.isdigit() and 1 <= int(score) <= 20, f"{n}: min_judge_score must be a whole number from 1 to 20")
            if fmt in DETAIL_RANK and parent in by_id and by_id[parent]["reporting_format"] in DETAIL_RANK:
                r.check(DETAIL_RANK[fmt] >= DETAIL_RANK[by_id[parent]["reporting_format"]],
                        f"{n}: sends less detail than its parent {parent}, but detail gets coarser going up")
    r.check(layers == set(range(len(layers))), f"layers {sorted(layers)} have a gap")
    r.check(len(layers) == EXPECTED["layers"], f"{len(layers)} layers, expected {EXPECTED['layers']}")

    # layer registry: names, roles and the transfer rule of each layer (Phase 6)
    layer_rows = r.load_csv(REGISTRY / "layer_registry.csv", LAYER_COLUMNS)
    tables = [body for _, _, body in md_tables(readme)]
    r.check(len(tables) >= 2 and [cells[0] for cells in tables[1]] == LAYER_COLUMNS,
            "registry README must document the layer_registry.csv columns in its second table")
    r.check(sorted(int(x["layer_index"]) for x in layer_rows if x["layer_index"].isdigit()) == sorted(layers),
            "layer_registry.csv must have one row for each layer the nodes use")
    rule_of = {}
    for row in layer_rows:
        i = row["layer_index"]
        r.check(i.isdigit(), f"layer {i}: layer_index must be a whole number")
        r.check(bool(row["name"].strip()) and bool(row["role"].strip()) and bool(row["source"].strip()),
                f"layer {i}: name, role and source must not be empty")
        level, score = row["detail_level"], row["min_judge_score"]
        if not level:
            r.check(not any(row[c] for c in LAYER_COLUMNS[4:11]), f"layer {i}: a layer that receives nothing has no rule fields")
            continue
        r.check(level in DETAIL_RANK, f"layer {i}: unknown detail_level {level}")
        r.check(score == "" or (score.isdigit() and 1 <= int(score) <= 20), f"layer {i}: min_judge_score must be empty or a whole number from 1 to 20")
        r.check(row["max_words"] == "" or (row["max_words"].isdigit() and int(row["max_words"]) >= 1), f"layer {i}: max_words must be empty or a whole number from 1")
        r.check(row["citation_level"] == "" or row["citation_level"] in CITATION_LEVELS, f"layer {i}: citation_level must be empty, short or long")
        required, excluded = [x for x in row["required_topics"].split(";") if x], [x for x in row["excluded_topics"].split(";") if x]
        r.check(len(set(required)) == len(required) and len(set(excluded)) == len(excluded), f"layer {i}: a topic is listed twice")
        r.check(not set(required) & set(excluded), f"layer {i}: a topic is both required and excluded")
        if i.isdigit() and level in DETAIL_RANK:
            rule_of[int(i)] = (level, score)
    for i, (level, _) in rule_of.items():
        if i + 1 in rule_of:
            r.check(DETAIL_RANK[level] <= DETAIL_RANK[rule_of[i + 1][0]],
                    f"layer {i} asks for more detail than layer {i + 1}, but detail gets coarser going up")
    for i in layers:
        if i + 1 in layers:
            r.check(i in rule_of, f"layer {i} receives packages from layer {i + 1}, so it needs a transfer rule")
    for row in rows:
        parent = by_id.get(row["parent_node_id"])
        if parent is not None and parent["layer_index"].isdigit() and int(parent["layer_index"]) in rule_of:
            level, score = rule_of[int(parent["layer_index"])]
            r.check(row["reporting_format"] == level,
                    f"{row['node_id']}: sends {row['reporting_format']}, but the rule of layer {parent['layer_index']} asks for {level}")
            r.check(score == "" or row["min_judge_score"] == score,
                    f"{row['node_id']}: minimum judge score {row['min_judge_score']}, but the rule of layer {parent['layer_index']} says {score}")

    # registry <-> documents
    for row in rows:
        n = row["node_id"]
        terminal = row["is_terminal"] == "true"
        docs = [m for m in manifest if m["node_id"] == n]
        r.check(bool(docs), f"{n}: no documents in the manifest")
        folders = {m["file"].split("/")[0] for m in docs}
        r.check(all(f.endswith("_TERMINAL") == terminal for f in folders), f"{n}: folder name ends in _TERMINAL only for terminal nodes")
        if terminal:
            r.check(not children[n], f"{n}: a terminal node must have no child nodes")
            r.check(len({m["doc_id"] for m in docs}) == 1, f"{n}: a terminal node has exactly one summary document")


# ---------------------------------------------------------------- validator 3
def check_scope_and_glossary(r):
    hygiene(r, SCOPE)
    hygiene(r, GLOSSARY)
    key_ids = {q["question_id"] for q in r.load_csv(CASE / "answer_key.csv", KEY_COLUMNS)}
    with (REGISTRY / "node_layer_registry.csv").open(encoding="utf-8", newline="") as f:
        registry_header = csv.DictReader(f).fieldnames

    # --- objectives and traceability
    objectives = r.load_csv(SCOPE / "objectives.csv", OBJECTIVE_COLUMNS)
    trace = r.load_csv(SCOPE / "proposal_traceability.csv", TRACE_COLUMNS)
    oids = [o["objective_id"] for o in objectives]
    r.check(oids == [f"O{i}" for i in range(1, EXPECTED["objectives"] + 1)], f"objective ids are {oids}, expected O1 to O{EXPECTED['objectives']}")
    r.check([t["proposal_objective"] for t in trace] == [str(i) for i in range(1, EXPECTED["proposal_objectives"] + 1)],
            f"traceability must list proposal objectives 1 to {EXPECTED['proposal_objectives']} once each")

    covered = set()
    for o in objectives:
        oid = o["objective_id"]
        r.check(re.fullmatch(r"\d+(;\d+)*", o["proposal_phases"]) is not None, f"{oid}: proposal_phases must look like 4;5")
        if re.fullmatch(r"\d+(;\d+)*", o["proposal_phases"]):
            r.check(all(1 <= int(p) <= 16 for p in o["proposal_phases"].split(";")), f"{oid}: phases must be between 1 and 16")
        questions = split_ids(o["answer_key_questions"])
        r.check(questions <= key_ids, f"{oid}: unknown questions {sorted(questions - key_ids)}")
        covered |= questions
        traced = {t["proposal_objective"] for t in trace if oid in split_ids(t["project_objectives"])}
        r.check(bool(traced), f"{oid}: no proposal objective maps to it")
        r.check(traced == split_ids(o["proposal_objectives"]),
                f"{oid}: proposal_objectives {sorted(split_ids(o['proposal_objectives']))} differ from traceability {sorted(traced)}")
        r.check(bool(o["target"].strip()), f"{oid}: target is empty (use the placeholder until it is agreed)")
    r.check(covered == key_ids, f"answer-key questions covered by no objective: {sorted(key_ids - covered)}")
    for t in trace:
        r.check(split_ids(t["project_objectives"]) <= set(oids), f"proposal objective {t['proposal_objective']}: unknown project objective")

    # --- the scope page repeats the objectives and the traceability
    scope_md = (SCOPE / "scope_and_objectives.md").read_text(encoding="utf-8")
    tables = list(md_tables(scope_md))
    obj_rows = next((body for _, h, body in tables if h == ["ID", "Objective", "Built in phase"]), None)
    cov_rows = next((body for _, h, body in tables if h == ["Proposal objective", "Summary", "Project objective"]), None)
    r.check(obj_rows is not None, "scope_and_objectives.md: objectives table not found")
    r.check(cov_rows is not None, "scope_and_objectives.md: coverage table not found")
    by_oid = {o["objective_id"]: o for o in objectives}
    for oid, text, phases in obj_rows or []:
        o = by_oid.get(oid)
        r.check(o is not None, f"scope_and_objectives.md lists unknown objective {oid}")
        if o:
            r.check(text == f"**{o['title']}.** {o['statement']}", f"{oid}: text differs between scope_and_objectives.md and objectives.csv")
            r.check(split_ids(phases, ",") == split_ids(o["proposal_phases"]), f"{oid}: phases differ between scope_and_objectives.md and objectives.csv")
    r.check({row[0] for row in obj_rows or []} == set(oids), "scope_and_objectives.md objectives table does not list the same objectives as objectives.csv")
    by_trace = {t["proposal_objective"]: t for t in trace}
    for num, summary, project in cov_rows or []:
        t = by_trace.get(num)
        r.check(t is not None, f"scope_and_objectives.md coverage lists unknown proposal objective {num}")
        if t:
            r.check(summary == t["summary"], f"proposal objective {num}: summary differs between the .md page and the CSV")
            r.check(split_ids(project, ",") == split_ids(t["project_objectives"]), f"proposal objective {num}: project objectives differ between the .md page and the CSV")
    r.check({row[0] for row in cov_rows or []} == set(by_trace), "scope_and_objectives.md coverage table does not list the same proposal objectives as the CSV")

    # --- glossary
    terms = r.load_csv(GLOSSARY / "glossary.csv", GLOSSARY_COLUMNS)
    r.check(len({t["term"].lower() for t in terms}) == len(terms), "a glossary term appears twice (one term, one meaning)")
    real_codes = [t["code_name"] for t in terms if t["code_name"] != CODE_NAME_PLACEHOLDER]
    r.check(len(set(real_codes)) == len(real_codes), "two terms share a code name")
    for t in terms:
        name, kind = t["term"], t["kind"]
        r.check(all(t[c].strip() for c in GLOSSARY_COLUMNS), f"{name}: an empty glossary field")
        r.check(kind in ("Entity", "Value object", "Concept"), f"{name}: unknown kind {kind}")
        r.check(t["context"] in CONTEXTS, f"{name}: unknown bounded context {t['context']}")
        if kind == "Concept":
            r.check(t["source"] in ("proposal text", "added by us"), f"{name}: a concept comes from 'proposal text' or 'added by us'")
            r.check(re.fullmatch(r"[a-z][a-z0-9_]*", t["code_name"]) is not None or t["code_name"] == CODE_NAME_PLACEHOLDER,
                    f"{name}: a concept's code name is snake_case or '{CODE_NAME_PLACEHOLDER}'")
        else:
            # Classes from the proposal's tables say "Proposal". Classes added when the domain model was designed (Phase 3)
            # say where the idea comes from, like a concept does.
            r.check(t["source"] in ("Proposal", "proposal text", "added by us"),
                    f"{name}: an entity or value object comes from 'Proposal', 'proposal text' or 'added by us'")
            r.check(t["code_name"] == name and re.fullmatch(r"[A-Z][A-Za-z0-9]*", name) is not None, f"{name}: class names are PascalCase and equal the term")

    # --- glossary.md repeats glossary.csv
    gmd = (GLOSSARY / "glossary.md").read_text(encoding="utf-8")
    md_rows = {}
    for heading, header, body in md_tables(gmd):
        if header == ["Term", "Meaning", "Kind", "Context", "Avoid"]:
            for cells in body:
                md_rows[cells[0]] = (heading, *cells[1:])
    csv_terms = {t["term"] for t in terms}
    r.check(set(md_rows) == csv_terms,
            f"glossary.md and glossary.csv differ: only in md {sorted(set(md_rows) - csv_terms)}, only in csv {sorted(csv_terms - set(md_rows))}")
    for t in terms:
        if t["term"] not in md_rows:
            continue
        kind = t["kind"] if t["kind"] != "Concept" else f"Concept ({t['source']})"
        r.check(md_rows[t["term"]] == (t["area"], t["meaning"], kind, t["context"], t["avoid"]),
                f"{t['term']}: glossary.md and glossary.csv say different things")

    # --- numbers written in prose must match the data
    said = re.search(r"of the (\d+) terms", gmd)
    r.check(said is not None and int(said.group(1)) == len(terms), f"glossary.md says {said.group(1) if said else '?'} terms, the CSV has {len(terms)}")
    areas = {t["area"] for t in terms}
    readme = (PROJECT / "README.md").read_text(encoding="utf-8")
    said = re.search(r"(\d+) terms in (\d+) areas", readme)
    r.check(said is not None and (int(said.group(1)), int(said.group(2))) == (len(terms), len(areas)),
            f"README.md says '{said.group(0) if said else '?'}', the glossary has {len(terms)} terms in {len(areas)} areas")

    # --- glossary words used as column names in the registry
    by_term = {t["term"]: t for t in terms}
    r.check(by_term.get("Field of activity", {}).get("code_name") in registry_header, "the registry column for 'Field of activity' must use its glossary code name")
    r.check(by_term.get("Terminal node", {}).get("code_name") in registry_header, "the registry column for 'Terminal node' must use its glossary code name")


# ---------------------------------------------------------------- validator 4
def normalize(text):
    """Lowercase, drop thousands separators, collapse spaces: how answers are normalized before grading."""
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower())
    return " ".join(text.split())


def compare_tables(r, label, got, want):
    """got and want are lists of rows (lists of cells); the first cell is the id."""
    r.check(got is not None, f"{label}: table not found")
    got_by = {row[0]: row for row in got or []}
    want_by = {row[0]: row for row in want}
    r.check(set(got_by) == set(want_by), f"{label}: ids differ, only in page {sorted(set(got_by) - set(want_by))}, only in CSV {sorted(set(want_by) - set(got_by))}")
    for key, row in want_by.items():
        if key in got_by:
            r.check(got_by[key] == row, f"{label} {key}: the page and the CSV say different things")


def check_metrics_and_testing(r):
    hygiene(r, METRICS)
    hygiene(r, GUIDES)
    key = r.load_csv(CASE / "answer_key.csv", KEY_COLUMNS)
    q_type = {q["question_id"]: q["type"] for q in key}
    objective_ids = {o["objective_id"] for o in r.load_csv(SCOPE / "objectives.csv", OBJECTIVE_COLUMNS)}
    metrics = r.load_csv(METRICS / "metrics.csv", METRIC_COLUMNS)
    rules = r.load_csv(METRICS / "grading_rules.csv", GRADING_COLUMNS)
    type_rules = r.load_csv(METRICS / "question_type_rules.csv", TYPE_RULE_COLUMNS)
    facts = r.load_csv(METRICS / "key_facts.csv", FACT_COLUMNS)
    hard = r.load_csv(METRICS / "hard_rules.csv", HARD_COLUMNS)
    rule_ids = [x["rule_id"] for x in rules]

    # metrics
    r.check([m["metric_id"] for m in metrics] == [f"M{i:02d}" for i in range(1, len(metrics) + 1)], "metric ids must run M01, M02, ... with no gaps")
    r.check(len(metrics) == EXPECTED["metrics"], f"{len(metrics)} metrics, expected {EXPECTED['metrics']}")
    for m in metrics:
        mid = m["metric_id"]
        used = split_ids(m["grading_rules"])
        asked = re.findall(r"Q\d\d", m["data"])
        phase = m["first_measured_in_phase"]
        r.check(m["objective_id"] in objective_ids, f"{mid}: unknown objective {m['objective_id']}")
        r.check(m["component"] in COMPONENTS, f"{mid}: unknown component {m['component']}")
        r.check(m["method"] in METHODS, f"{mid}: unknown method {m['method']}")
        r.check(m["direction"] in ("higher", "lower"), f"{mid}: direction must be higher or lower")
        r.check(phase.isdigit() and 1 <= int(phase) <= 16, f"{mid}: first_measured_in_phase must be 1 to 16")
        r.check(all(m[c].strip() for c in ("name", "definition", "unit", "data")), f"{mid}: empty name, definition, unit or data")
        r.check(used <= set(rule_ids), f"{mid}: unknown grading rules {sorted(used - set(rule_ids))}")
        for q in asked:
            r.check(q in q_type, f"{mid}: unknown question {q}")
        if asked and used:
            refusal = [q_type.get(q) in REFUSAL_TYPES for q in asked]
            if used <= {"GR2"}:
                r.check(all(refusal), f"{mid}: GR2 applies to refusal questions only")
            else:
                r.check(not any(refusal), f"{mid}: these grading rules apply to answerable questions only")
        r.check(m["target"] == TARGET_PLACEHOLDER or bool(m["target_source"].strip()), f"{mid}: a target needs a target_source (who agreed it, and when)")
        r.check(m["baseline"] == "" or bool(m["baseline_source"].strip()), f"{mid}: a baseline needs a baseline_source (which run produced it)")
    for oid in sorted(objective_ids):
        r.check(any(m["objective_id"] == oid for m in metrics), f"{oid} has no metric")

    # grading rules and question types
    r.check(rule_ids == [f"GR{i}" for i in range(1, len(rule_ids) + 1)], "grading rule ids must run GR1, GR2, ... with no gaps")
    r.check(all(x["automatic"] in ("yes", "partly", "no") for x in rules), "automatic must be yes, partly or no")
    r.check({t["question_type"] for t in type_rules} == set(q_type.values()), "question_type_rules.csv must cover exactly the question types of the answer key")
    for t in type_rules:
        used = split_ids(t["grading_rules"])
        r.check(bool(used) and used <= set(rule_ids), f"{t['question_type']}: grading rules missing or unknown")

    # key facts must match the expected answers of the answer key
    r.check([f["question_id"] for f in facts] == [q["question_id"] for q in key], "key_facts.csv must list every question once, in answer-key order")
    expected = {q["question_id"]: normalize(q["expected_answer"]) for q in key}
    for f in facts:
        qid = f["question_id"]
        if qid not in q_type:
            continue
        groups = [g for g in f["required"].split(";") if g]
        r.check(bool(groups) != (q_type[qid] in REFUSAL_TYPES), f"{qid}: list required facts unless it is a refusal question")
        for g in groups:
            alternatives = [a.strip() for a in g.split("|")]
            r.check(all(alternatives), f"{qid}: empty alternative in '{g}'")
            r.check(any(a in expected[qid] for a in alternatives), f"{qid}: none of '{g}' appears in the expected answer")
        for bad in [b.strip() for b in f["forbidden"].split(";") if b]:
            r.check(bad in expected[qid], f"{qid}: forbidden fact '{bad}' is not in the expected answer")
        if q_type[qid] == "node_boundary":
            r.check(bool(f["forbidden"]), f"{qid}: a node_boundary question must list what must not leak")

    # hard rules
    r.check([h["rule_id"] for h in hard] == [f"H{i:02d}" for i in range(1, len(hard) + 1)], "hard rule ids must run H01, H02, ... with no gaps")
    r.check(len(hard) == EXPECTED["hard_rules"], f"{len(hard)} hard rules, expected {EXPECTED['hard_rules']}")
    for h in hard:
        r.check(h["objective_id"] in objective_ids, f"{h['rule_id']}: unknown objective {h['objective_id']}")
        r.check(bool(h["statement"].strip() and h["how_tested"].strip()), f"{h['rule_id']}: empty statement or how_tested")

    # metrics.md repeats the CSV files
    page = (METRICS / "metrics.md").read_text(encoding="utf-8")
    tables = {tuple(h): body for _, h, body in md_tables(page)}
    compare_tables(r, "metrics.md metrics", tables.get(("ID", "Metric", "Objective", "Component", "Method", "First measured in phase")),
                   [[m["metric_id"], m["name"], m["objective_id"], m["component"], m["method"], m["first_measured_in_phase"]] for m in metrics])
    compare_tables(r, "metrics.md hard rules", tables.get(("ID", "Objective", "Rule", "Tested by")),
                   [[h["rule_id"], h["objective_id"], h["statement"], h["how_tested"]] for h in hard])
    compare_tables(r, "metrics.md grading", tables.get(("Question type", "Grading rules")),
                   [[t["question_type"], ", ".join(sorted(split_ids(t["grading_rules"])))] for t in type_rules])

    # the unit-testing page assigns every hard rule and every objective to a test area
    testing_md = (GUIDES / "unit_testing_rules.md").read_text(encoding="utf-8")
    areas = next((body for _, h, body in md_tables(testing_md) if h[:1] == ["Area"]), [])
    r.check(len(areas) == EXPECTED["test_areas"], f"{len(areas)} test areas, expected {EXPECTED['test_areas']}")
    r.check(len({a[0] for a in areas}) == len(areas), "a test area appears twice")
    assigned = set().union(*[split_ids(a[2], ",") for a in areas]) if areas else set()
    for h in hard:
        r.check(h["rule_id"] in assigned, f"{h['rule_id']} is not assigned to any test area in unit_testing_rules.md")
    covered = {a[3] for a in areas}
    for oid in sorted(objective_ids):
        r.check(oid in covered, f"{oid} has no test area in unit_testing_rules.md")


# ---------------------------------------------------------------- validator 5
PROJECT_PATH_PREFIXES = ("case_study/", "registry/", "scope/", "glossary/", "metrics/", "models/", "prompts/", "experiments/",
                         "docs/", "baseline_runner/", "tests/", "scripts/", "tools/", "source/", "study_notes/",
                         "architecture/", "rag_core/")


def check_paths_exist(r, page_path):
    """Every `path/to/file.ext` written in backticks and starting at the project root must exist."""
    text = page_path.read_text(encoding="utf-8")
    for p in sorted(set(re.findall(r"`([\w./-]+\.(?:md|csv|py|txt))`", text))):
        if p.startswith(PROJECT_PATH_PREFIXES):
            r.check((PROJECT / p).exists(), f"{page_path.name} mentions a file that does not exist: {p}")


def check_report(r):
    report_path = GUIDES / "domain_discovery_report.md"
    text = report_path.read_text(encoding="utf-8")
    manifest = r.load_csv(CASE / "documents_manifest.csv", MANIFEST_COLUMNS)
    registry = r.load_csv(REGISTRY / "node_layer_registry.csv", REGISTRY_COLUMNS)
    terms = r.load_csv(GLOSSARY / "glossary.csv", GLOSSARY_COLUMNS)
    metrics = r.load_csv(METRICS / "metrics.csv", METRIC_COLUMNS)
    hard = r.load_csv(METRICS / "hard_rules.csv", HARD_COLUMNS)

    table = next((body for _, h, body in md_tables(text) if h == ["Node", "Layer", "Terminal", "Files"]), None)
    compare_tables(r, "domain_discovery_report.md node table", table,
                   [[n["node_id"], n["layer_index"], "yes" if n["is_terminal"] == "true" else "no",
                     str(sum(1 for m in manifest if m["node_id"] == n["node_id"]))] for n in registry])

    # numbers written in prose must match the data
    said = re.search(r"(\d+) nodes, (\d+) documents in (\d+) files, (\d+) issues, (\d+) people and (\d+) test questions", text)
    want = tuple(EXPECTED[k] for k in ("nodes", "documents", "files", "issues", "people", "questions"))
    r.check(said is not None and tuple(int(x) for x in said.groups()) == want, f"the report's case-study numbers differ from {want}")
    said = re.search(r"(\d+) terms with one meaning", text)
    r.check(said is not None and int(said.group(1)) == len(terms), f"the report says {said.group(1) if said else '?'} terms, the glossary has {len(terms)}")
    said = re.search(r"(\d+) metrics and (\d+) hard rules", text)
    r.check(said is not None and (int(said.group(1)), int(said.group(2))) == (len(metrics), len(hard)),
            f"the report says '{said.group(0) if said else '?'}', the data has {len(metrics)} metrics and {len(hard)} hard rules")
    check_paths_exist(r, report_path)

    notes = PROJECT / "study_notes"
    hygiene(r, notes)
    for page in sorted(notes.glob("*.md")):
        check_paths_exist(r, page)


# ---------------------------------------------------------------- validator 6
MODEL_COLUMNS = [
    "model_id", "task", "runtime_tag", "parameters", "quantization", "download_gb", "context_tokens", "input", "license",
    "languages", "thinking_listed", "status", "tier", "fit_estimate", "limits", "evaluation_notes", "source_url",
    "license_source", "verified_on",
]
PROMPT_COLUMNS = ["prompt_id", "task", "version", "file", "placeholders", "applies_to", "notes"]
EXPERIMENT_COLUMNS = ["exp_id", "name", "task", "question", "metrics", "prompts", "models", "notes"]
PROBE_COLUMNS = ["probe_id", "question_id", "candidate", "label", "gr1_blind_spot"]
MODEL_TASKS = {"embedding", "llm", "lvm"}
MODEL_STATUSES = {"candidate", "shortlisted", "baseline", "rejected"}
PROMPT_TASKS = {"answer", "read_page", "judge", "embed_query", "embed_document", "suggest_sub_issues"}
FREE_VRAM_GB = 2.9    # 4096 MiB of GPU memory minus the 1168 MiB that Windows used when we measured
MEMORY_FACTOR = 1.2   # weights plus about 20 percent: the rough rule of chapter 7 of the book


def check_phase2(r):
    for folder in ("models", "prompts", "experiments"):
        hygiene(r, PROJECT / folder)
    models = r.load_csv(PROJECT / "models" / "model_registry.csv", MODEL_COLUMNS)
    prompts = r.load_csv(PROJECT / "prompts" / "prompt_registry.csv", PROMPT_COLUMNS)
    experiments = r.load_csv(PROJECT / "experiments" / "experiments.csv", EXPERIMENT_COLUMNS)
    probes = r.load_csv(PROJECT / "experiments" / "judge_probe.csv", PROBE_COLUMNS)
    metrics = r.load_csv(METRICS / "metrics.csv", METRIC_COLUMNS)
    question_ids = {q["question_id"] for q in r.load_csv(CASE / "answer_key.csv", KEY_COLUMNS)}

    # model registry
    ids = [m["model_id"] for m in models]
    r.check(len(set(ids)) == len(ids), "model_id repeats")
    r.check(len({m["runtime_tag"] for m in models}) == len(models), "runtime_tag repeats")
    for m in models:
        mid = m["model_id"]
        r.check(re.fullmatch(r"[a-z0-9.\-]+", mid) is not None, f"{mid}: model ids use lowercase letters, digits, dots and dashes")
        r.check(m["task"] in MODEL_TASKS, f"{mid}: unknown task {m['task']}")
        r.check(m["status"] in MODEL_STATUSES, f"{mid}: unknown status {m['status']}")
        r.check(m["thinking_listed"] in ("yes", "no"), f"{mid}: thinking_listed must be yes or no")
        r.check(m["tier"] in ("1", "2", "3"), f"{mid}: tier must be 1, 2 or 3")
        r.check(m["context_tokens"].isdigit(), f"{mid}: context_tokens must be a whole number")
        r.check(m["source_url"].startswith("https://") and m["license_source"].startswith("https://"), f"{mid}: source_url and license_source must be https addresses")
        r.check(re.fullmatch(r"\d{4}-\d{2}-\d{2}", m["verified_on"]) is not None, f"{mid}: verified_on must be YYYY-MM-DD")
        r.check(all(m[c].strip() for c in ("parameters", "quantization", "input", "license", "languages", "limits")),
                f"{mid}: an empty cell, write 'not stated' or 'not checked' instead")
        try:
            size = float(m["download_gb"])
        except ValueError:
            r.fail(f"{mid}: download_gb must be a number")
        else:
            expected_fit = "fits GPU" if size * MEMORY_FACTOR <= FREE_VRAM_GB else "needs CPU offload"
            r.check(size > 0 and m["fit_estimate"] == expected_fit, f"{mid}: fit_estimate should be '{expected_fit}' for {size} GB")
        if m["status"] in ("baseline", "rejected"):
            r.check(bool(m["evaluation_notes"].strip()), f"{mid}: a {m['status']} model needs evaluation_notes")
    for task in sorted(MODEL_TASKS):
        r.check(any(m["task"] == task and m["status"] in ("shortlisted", "baseline") for m in models), f"no shortlisted {task} model")

    # prompt registry
    prompt_ids = [p["prompt_id"] for p in prompts]
    r.check(prompt_ids == [f"P{i:02d}" for i in range(1, len(prompts) + 1)], "prompt ids must run P01, P02, ... with no gaps")
    for p in prompts:
        path = PROJECT / "prompts" / p["file"]
        r.check(p["task"] in PROMPT_TASKS, f"{p['prompt_id']}: unknown task {p['task']}")
        r.check(p["version"].isdigit(), f"{p['prompt_id']}: version must be a whole number")
        r.check(path.exists(), f"{p['prompt_id']}: missing file {p['file']}")
        if path.exists():
            r.check(path.stem.endswith(f"_v{p['version']}"), f"{p['prompt_id']}: the file name must end in _v{p['version']}")
            blanks = set(re.findall(r"\{\{(\w+)\}\}", path.read_text(encoding="utf-8")))
            r.check(blanks == split_ids(p["placeholders"]), f"{p['prompt_id']}: blanks in the file {sorted(blanks)} differ from the registry")
        for target in split_ids(p["applies_to"]):
            r.check(target in ids or re.fullmatch(r"task:(llm|lvm|embedding)", target) is not None, f"{p['prompt_id']}: applies_to unknown model {target}")
    on_disk = {f.name for f in (PROJECT / "prompts").glob("*.txt")}
    r.check(on_disk == {p["file"] for p in prompts}, f"prompt files and the registry differ: {sorted(on_disk ^ {p['file'] for p in prompts})}")

    # experiments
    r.check([e["exp_id"] for e in experiments] == [f"E{i}" for i in range(1, len(experiments) + 1)], "experiment ids must run E1, E2, ... with no gaps")
    metric_ids = {m["metric_id"] for m in metrics}
    covered = set()
    for e in experiments:
        used = split_ids(e["metrics"])
        covered |= used
        r.check(e["task"] in MODEL_TASKS, f"{e['exp_id']}: unknown task {e['task']}")
        r.check(used <= metric_ids, f"{e['exp_id']}: unknown metrics {sorted(used - metric_ids)}")
        r.check(split_ids(e["prompts"]) <= set(prompt_ids), f"{e['exp_id']}: unknown prompts {sorted(split_ids(e['prompts']) - set(prompt_ids))}")
    phase2_metrics = {m["metric_id"] for m in metrics if m["first_measured_in_phase"] == "2"}
    r.check(phase2_metrics <= covered, f"metrics due in the model baseline that no experiment measures: {sorted(phase2_metrics - covered)}")
    plan = (GUIDES / "prompt_test_plan.md").read_text(encoding="utf-8")
    plan_table = next((body for _, h, body in md_tables(plan) if h == ["ID", "Experiment", "Metrics"]), None)
    compare_tables(r, "prompt_test_plan.md experiments", plan_table,
                   [[e["exp_id"], e["name"], ", ".join(sorted(split_ids(e["metrics"])))] for e in experiments])

    # judge probe
    r.check(len({p["probe_id"] for p in probes}) == len(probes), "probe ids repeat")
    labels = defaultdict(list)
    for p in probes:
        r.check(p["question_id"] in question_ids, f"{p['probe_id']}: unknown question {p['question_id']}")
        r.check(p["label"] in ("right", "wrong") and p["gr1_blind_spot"] in ("yes", "no"), f"{p['probe_id']}: label must be right or wrong, gr1_blind_spot yes or no")
        labels[p["question_id"]].append(p["label"])
    for qid in sorted(question_ids):
        r.check(labels[qid].count("right") == 1 and labels[qid].count("wrong") >= 1, f"{qid}: needs one right and at least one wrong probe answer")

    # the review names every shortlisted model, and the pages point only at files that exist
    review = (GUIDES / "model_review.md").read_text(encoding="utf-8")
    for m in models:
        if m["status"] in ("shortlisted", "baseline"):
            r.check(m["runtime_tag"].split(":")[0] in review, f"model_review.md does not mention {m['runtime_tag']}")
    for page in sorted(GUIDES.glob("*.md")):
        check_paths_exist(r, page)


VALIDATORS = [
    ("case_study", check_case_study),
    ("registry", check_registry),
    ("scope_and_glossary", check_scope_and_glossary),
    ("metrics_and_testing", check_metrics_and_testing),
    ("domain_report", check_report),
    ("models_and_experiments", check_phase2),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    failed = 0
    for name, validator in VALIDATORS:
        report = Report(name)
        try:
            validator(report)
        except Abort:
            pass  # the reason is already in report.problems
        except Exception as e:  # a missing file, for example
            report.fail(f"crashed: {type(e).__name__}: {e}")
        status = "FAIL" if report.problems else "PASS"
        print(f"[{status}] {name}: {report.checks} checks")
        for problem in report.problems:
            print(f"    - {problem}")
        failed += bool(report.problems)
    print(f"\n{len(VALIDATORS) - failed} of {len(VALIDATORS)} validators passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
