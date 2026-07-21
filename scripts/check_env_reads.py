#!/usr/bin/env python3
"""Fail if environment access appears outside ``config/`` (spec 08 §1.4, spec 09 §9 gate 10).

The single-reader rule: only ``korchestrator.config`` may read ``os.environ`` / ``os.getenv``
or load a ``.env`` file. Every other module receives configuration by injection. This gate
greps the package source and exits non-zero if any other module reaches the environment.
"""

from __future__ import annotations

import pathlib
import re
import sys

FORBIDDEN = re.compile(r"\b(os\.environ|os\.getenv|load_dotenv|dotenv_values)\b")
PACKAGE = pathlib.Path("src/korchestrator")


def main() -> int:
    """Scan the package for out-of-bounds environment reads; return an exit code."""
    if not PACKAGE.is_dir():
        print(f"FAIL: {PACKAGE} not found", file=sys.stderr)
        return 1

    offenders = [
        str(path)
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.parts[2] != "config" and FORBIDDEN.search(path.read_text(encoding="utf-8"))
    ]

    if offenders:
        print(f"FAIL: environment read outside config/: {offenders}", file=sys.stderr)
        return 1

    print("env-reads OK: environment is read only inside config/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
