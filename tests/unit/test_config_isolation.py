"""Config isolation gate (spec 08 §1.4): environment access is confined to ``config/``.

Reuses ``scripts.check_env_reads.find_offenders`` — the same scan the standalone
``python scripts/check_env_reads.py`` CI/pre-commit gate runs — so there is one canonical
implementation of this check, not two that could drift apart.
"""

from __future__ import annotations

import pathlib

from scripts.check_env_reads import find_offenders

_PACKAGE = pathlib.Path("src/korchestrator")


def test_environment_is_read_only_inside_config() -> None:
    assert find_offenders(_PACKAGE) == []


def test_the_scan_actually_detects_an_offender(tmp_path: pathlib.Path) -> None:
    # A regression guard for the check itself: prove it flags a real violation, not just that the
    # real package happens to pass (a scan that always returns [] would pass the test above too).
    package = tmp_path / "korchestrator"
    (package / "config").mkdir(parents=True)
    (package / "routing").mkdir()
    (package / "config" / "settings.py").write_text("import os\nos.environ.get('X')\n")
    (package / "routing" / "factory.py").write_text("import os\nos.environ.get('X')\n")

    offenders = find_offenders(package)

    assert len(offenders) == 1
    assert "routing" in offenders[0]
