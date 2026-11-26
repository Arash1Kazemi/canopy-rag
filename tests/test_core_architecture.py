"""The dependency rule of architecture/architecture.md, checked on the code itself.

The domain (shared, organization, knowledge, rag, issues) and the ports (models) may import only the standard library
and each other. They never import the application layer, the adapters, the Phase 2 runner, or anything that reaches
files on disk, databases, processes or the network. Every package of rag_core must be given a layer here, so a new
package cannot slip past the rule (build plan A3).
"""
import ast
from pathlib import Path

import pytest

CORE = Path("rag_core")
DOMAIN = ("shared", "organization", "knowledge", "rag", "models", "issues")
DOMAIN = DOMAIN + ("executors",)   # Phase 9: Executor Management is domain code
DOMAIN = DOMAIN + ("ike",)         # Phase 9: the Issue-Knowledge-Executor model is domain code
DOMAIN = DOMAIN + ("judging",)     # Phase 10: the rubric, the score parser, the thresholds and the judge use case are domain code
FORBIDDEN_PACKAGES = ("rag_core.ingestion", "rag_core.infrastructure", "rag_core.workflows", "baseline_runner")
FORBIDDEN_MODULES = {"sqlite3", "socket", "urllib", "http", "requests", "subprocess", "zipfile", "pathlib", "os", "shutil"}


def imports_of(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = ".".join(path.relative_to(CORE.parent).with_suffix("").parts[:-1])
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:   # a relative import: resolve it against this file's package
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                names.append(".".join(base + ([node.module] if node.module else [])))
            else:
                names.append(node.module)
    return names


@pytest.mark.parametrize("path", [p for d in DOMAIN for p in sorted((CORE / d).glob("*.py"))], ids=str)
def test_the_domain_imports_nothing_from_outer_layers(path):
    for name in imports_of(path):
        assert not name.startswith(FORBIDDEN_PACKAGES), f"{path} imports {name}"
        assert name.split(".")[0] not in FORBIDDEN_MODULES, f"{path} imports {name}"


APPLICATION = ("ingestion", "workflows")


@pytest.mark.parametrize("path", [p for d in APPLICATION for p in sorted((CORE / d).glob("*.py"))], ids=str)
def test_the_application_layer_does_not_import_adapters(path):
    for name in imports_of(path):
        assert not name.startswith(("rag_core.infrastructure", "baseline_runner")), f"{path} imports {name}"


INFRASTRUCTURE = ("infrastructure",)


def test_every_package_has_a_layer():
    packages = {p.parent.name for p in CORE.glob("*/__init__.py")}
    unknown = packages - set(DOMAIN) - set(APPLICATION) - set(INFRASTRUCTURE)
    assert not unknown, f"give these packages a layer in this test: {sorted(unknown)}"


def test_the_issue_domain_is_checked():
    checked = {p.name for p in (CORE / "issues").glob("*.py")}
    assert {"model.py", "status.py", "progress.py", "rules.py", "comparison.py", "suggestions.py", "repository.py"} <= checked


def test_the_rag_domain_is_checked():
    """Phase 8: the vector index, indexing and retrieval are domain code; their adapters live in infrastructure."""
    checked = {p.name for p in (CORE / "rag").glob("*.py")}
    assert {"citation.py", "vector_index.py", "indexing.py", "retrieval.py"} <= checked
    for adapter in ("memory.py", "sqlite_vectors.py", "ollama_embedding.py"):
        assert (CORE / "infrastructure" / adapter).is_file()


def test_the_executor_domain_is_checked():
    """Phase 9: executors and matching are domain code; the adapters live in infrastructure."""
    checked = {p.name for p in (CORE / "executors").glob("*.py")}
    assert {"model.py", "matching.py", "repository.py"} <= checked
    for adapter in ("memory.py", "sqlite_executors.py", "executors_csv.py"):
        assert (CORE / "infrastructure" / adapter).is_file()


def test_the_ike_domain_is_checked():
    """Phase 9: the IKE model, its rules, seed and summary are domain code; the adapters live in infrastructure."""
    checked = {p.name for p in (CORE / "ike").glob("*.py")}
    assert {"model.py", "rules.py", "seed.py", "summary.py", "repository.py"} <= checked
    for adapter in ("memory_ike.py", "sqlite_ike.py"):
        assert (CORE / "infrastructure" / adapter).is_file()


def test_the_judging_domain_is_checked():
    """Phase 10: the rubric, parser, threshold policy, judge use case and stored scores are domain code; the adapters live in
    infrastructure and the prompt loader in workflows."""
    checked = {p.name for p in (CORE / "judging").glob("*.py")}
    assert {"rubric.py", "parser.py", "threshold.py", "model.py", "prompt.py", "judge.py", "repository.py"} <= checked
    for adapter in ("memory_judging.py", "sqlite_judging.py"):
        assert (CORE / "infrastructure" / adapter).is_file()
    assert (CORE / "workflows" / "judge_prompts.py").is_file()


def test_the_judge_never_imports_the_model_adapter():
    """The judge takes the LanguageModel port as an argument (unit-testing rule 1); only the command line builds the Ollama adapter."""
    for path in (CORE / "judging").glob("*.py"):
        assert not any(name.startswith(("rag_core.infrastructure", "baseline_runner")) or name.endswith("ollama_language")
                       for name in imports_of(path)), path
