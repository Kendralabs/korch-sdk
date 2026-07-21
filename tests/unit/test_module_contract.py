"""Module-contract tests: every package declares its layer and its public surface.

Locks the skeleton contract from spec 05 §2 — each package under ``korchestrator`` has an
explicit ``__all__`` and a docstring naming its layer. This fails the moment a package is
added without those, or one is removed from the expected set.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import korchestrator

# The authoritative set of packages from spec 05 §1. Kept explicit (not just discovered) so
# an accidental deletion or a stray new top-level package fails this test loudly.
EXPECTED_PACKAGES = frozenset(
    {
        "config",
        "interfaces",
        "models",
        "core",
        "agents",
        "taxonomy",
        "routing",
        "runtime",
        "context",
        "persistence",
        "providers",
        "tools",
        "mcp",
        "a2a",
        "governance",
        "security",
        "events",
        "clients",
        "services",
        "serializers",
        "validators",
        "telemetry",
        "logging",
        "exceptions",
        "types",
        "constants",
    }
)

DISCOVERED_PACKAGES = frozenset(
    info.name for info in pkgutil.iter_modules(korchestrator.__path__) if info.ispkg
)


def test_discovered_packages_match_the_spec_catalogue() -> None:
    assert DISCOVERED_PACKAGES == EXPECTED_PACKAGES


@pytest.mark.parametrize("package", sorted(EXPECTED_PACKAGES))
def test_package_declares_explicit_all(package: str) -> None:
    module = importlib.import_module(f"korchestrator.{package}")
    assert isinstance(module.__all__, list)


@pytest.mark.parametrize("package", sorted(EXPECTED_PACKAGES))
def test_package_docstring_names_its_layer(package: str) -> None:
    module = importlib.import_module(f"korchestrator.{package}")
    docstring = module.__doc__ or ""
    assert docstring.strip(), f"korchestrator.{package} has no module docstring"
    assert "layer" in docstring.lower(), f"korchestrator.{package} docstring must name its layer"


def test_top_level_package_exposes_version() -> None:
    assert korchestrator.__all__ == ["__version__"]
    assert korchestrator.__version__ == "0.1.0"
