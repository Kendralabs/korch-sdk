#!/usr/bin/env python3
"""Fail if environment access appears outside ``config/`` (spec 08 §1.4, spec 09 §9 gate 10).

The single-reader rule: only ``korchestrator.config`` may read ``os.environ`` / ``os.getenv``
or load a ``.env`` file. Every other module receives configuration by injection. This gate
greps the package source and exits non-zero if any other module reaches the environment.

The scan itself (:func:`find_offenders`) is also imported directly by
``tests/unit/test_config_isolation.py`` (spec 08 §1.4's own pytest requirement), so there is one
canonical implementation of the check, exercised both by this standalone CLI script and by the
normal ``pytest`` run.
"""

from __future__ import annotations

import pathlib
import re
import sys

FORBIDDEN = re.compile(r"\b(os\.environ|os\.getenv|load_dotenv|dotenv_values)\b")
PACKAGE = pathlib.Path("src/korchestrator")


def find_offenders(package: pathlib.Path = PACKAGE) -> list[str]:
    """Return the paths, under ``package``, outside ``config/`` that read the environment."""
    return [
        str(path)
        for path in sorted(package.rglob("*.py"))
        if path.relative_to(package).parts[0] != "config"
        and FORBIDDEN.search(path.read_text(encoding="utf-8"))
    ]


def main() -> int:
    """Scan the package for out-of-bounds environment reads; return an exit code."""
    if not PACKAGE.is_dir():
        print(f"FAIL: {PACKAGE} not found", file=sys.stderr)
        return 1

    offenders = find_offenders(PACKAGE)

    if offenders:
        print(f"FAIL: environment read outside config/: {offenders}", file=sys.stderr)
        return 1

    print("env-reads OK: environment is read only inside config/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
