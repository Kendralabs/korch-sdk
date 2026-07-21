"""Smoke test: a freshly installed package imports and reports its version.

Runs in the base-install CI job (pydantic-only). Spec 02 §4 / spec 09 §2 define the smoke
type as "import, ``__version__``, and the Tier-1 one-liner"; the one-liner
(``Korch().run(...)``) lands in P4, at which point this test grows to cover it.
"""

from __future__ import annotations

import korchestrator


def test_package_imports_and_reports_version() -> None:
    assert korchestrator.__version__ == "0.1.0"
    assert "__version__" in korchestrator.__all__


def test_settings_construct_on_a_pydantic_only_install() -> None:
    # ADR 0009: config works on the base install with no pydantic-settings.
    from korchestrator.config import Settings

    assert Settings().korch_runtime == "local"
