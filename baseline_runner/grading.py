"""The grading rules GR1 to GR5 of metrics/grading_rules.csv.

A rule decides whether one answer is correct. It reads only the answer and the key facts, so it gives
the same result on every run.
"""
import re

from .config import METRICS, REFUSAL_PHRASE
from .corpus import read_csv


def normalize(text):
    """Lowercase, drop thousands separators (8,200 becomes 8200), collapse spaces."""
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower())
    return " ".join(text.split())


def load_key_facts(path=METRICS / "key_facts.csv"):
    """question id -> {"required": [[alternative, ...], ...], "forbidden": [fact, ...]}"""
    facts = {}
    for row in read_csv(path):
        facts[row["question_id"]] = {
            "required": [[a.strip() for a in group.split("|")] for group in row["required"].split(";") if group],
            "forbidden": [b.strip() for b in row["forbidden"].split(";") if b],
        }
    return facts


def load_type_rules(path=METRICS / "question_type_rules.csv"):
    return {r["question_type"]: set(r["grading_rules"].split(";")) for r in read_csv(path)}


def key_facts_present(answer, key_facts):
    """GR1: every required fact is there (one alternative per group is enough), and no forbidden fact."""
    text = normalize(answer)
    has_all = all(any(alternative in text for alternative in group) for group in key_facts["required"])
    return has_all and not any(fact in text for fact in key_facts["forbidden"])


def refusal_phrase(answer, key_facts):
    """GR2: the answer says insufficient knowledge, and leaks none of the forbidden facts."""
    text = normalize(answer)
    return REFUSAL_PHRASE in text and not any(fact in text for fact in key_facts["forbidden"])


def says_refusal(answer):
    """The phrase check alone, used for false refusals (M04)."""
    return REFUSAL_PHRASE in normalize(answer)


def parse_citations(answer):
    """The file stems written in square brackets, such as [D10_bus_fleet_inventory_v2]. Only D-ids count."""
    stems = []
    for bracket in re.findall(r"\[([^\[\]]+)\]", answer):
        for part in re.split(r"[,;]", bracket):
            stem = part.strip()
            stem = stem[:-3] if stem.lower().endswith(".md") else stem
            if re.match(r"D\d\d", stem):
                stems.append(stem)
    return stems


def gold_groups(source_files, all_stems):
    """The answer-key sources of a question as groups of acceptable file stems, one group per source.
    D11 means any file of document D11. D12_driver_shift_rules (or its copy) accepts both files."""
    copy_ok = "or its copy" in source_files
    groups = []
    for token in re.findall(r"D\d\d(?:_[A-Za-z0-9_\-]+)?", source_files):  # the hyphen is in D19_meeting_minutes_2025-06-18
        if "_" in token:
            groups.append({token} | ({token + "_copy"} if copy_ok else set()))
        else:
            groups.append({s for s in all_stems if s == token or s.startswith(token + "_")})
    return groups


def citations_valid(cited, groups):
    """GR5: at least one citation, and every cited file is an answer-key source."""
    gold = set().union(*groups) if groups else set()
    return bool(cited) and all(c in gold for c in cited)


def duplicate_cited_once(cited, doc_id="D12"):
    """GR4: exactly one file of the duplicated document is cited, not the file and its copy."""
    return len({c for c in cited if c == doc_id or c.startswith(doc_id + "_")}) == 1


def grade_answer(question, key_facts, answer, type_rules, all_stems):
    """Apply the rules of the question's type. Returns ({rule id: passed}, cited stems).
    GR3 is GR1 for a question whose required facts include both sources and a conflict word."""
    rules = type_rules[question["type"]]
    cited = parse_citations(answer)
    results = {}
    if "GR1" in rules:
        results["GR1"] = key_facts_present(answer, key_facts)
    if "GR2" in rules:
        results["GR2"] = refusal_phrase(answer, key_facts)
    if "GR3" in rules:
        results["GR3"] = key_facts_present(answer, key_facts)
    if "GR4" in rules:
        results["GR4"] = duplicate_cited_once(cited)
    if "GR5" in rules:
        results["GR5"] = citations_valid(cited, gold_groups(question["source_files"], all_stems))
    return results, cited


def is_correct(results):
    """Correct means every rule except the citation rule passed. Citations are scored on their own (M02)."""
    return all(passed for rule, passed in results.items() if rule != "GR5")
