"""Tier 4 re-export surface tests (spec 04 §2/§7, P9.1)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("httpx")

from korchestrator.clients import (
    KorchestratorClient as _ClientsKorchestratorClient,
)
from korchestrator.remote import KorchestratorClient


def test_remote_reexports_the_same_class_clients_owns() -> None:
    # korchestrator.remote is a thin re-export, not a second implementation (one canonical source).
    assert KorchestratorClient is _ClientsKorchestratorClient


def test_the_base_package_source_never_imports_clients_or_remote() -> None:
    # A base `import korchestrator` must never pull in httpx; whether it does depends on whether
    # __init__.py's own source imports `clients`/`remote` — checked statically (not via sys.modules,
    # which sibling test modules in this same process may have already populated either way).
    import korchestrator

    source = Path(korchestrator.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) if node.module
    }
    assert "clients" not in imported_names
    assert "remote" not in imported_names
    assert not any(m.endswith(("clients", "remote")) for m in imported_modules)
