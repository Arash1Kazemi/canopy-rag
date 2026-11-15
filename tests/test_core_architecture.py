"""The dependency rule of architecture/architecture.md, checked on the code itself.

The domain (shared, organization, knowledge, rag) and the ports (models) may import only the standard library and
each other. They never import the application layer, the adapters, the Phase 2 runner, or anything that reaches
files on disk, databases, processes or the network.
"""
import ast
from pathlib import Path

import pytest

CORE = Path("rag_core")
DOMAIN = ("shared", "organization", "knowledge", "rag", "models")
FORBIDDEN_PACKAGES = ("rag_core.ingestion", "rag_core.infrastructure", "baseline_runner")
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
