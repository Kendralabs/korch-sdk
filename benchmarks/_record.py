"""Shared helper: record one benchmark's measurements into benchmarks/baseline.json (spec 09 §8).

Benchmarks are informational, never blocking (spec 09 §8) — this only ever *records* a result
next to the commit SHA that produced it; comparing against history and deciding whether a change
is a regression is a human judgment call made in the deliberate PR that updates the baseline, not
something this module enforces.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

__all__ = ["record"]

_BASELINE_PATH = Path(__file__).parent / "baseline.json"


def _commit_sha() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 — "git" via PATH is fine for dev tooling
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }


def record(benchmark: str, measurements: dict[str, Any]) -> None:
    """Merge ``measurements`` for ``benchmark`` into ``benchmarks/baseline.json``.

    Overwrites this benchmark's own entry (keyed by name); leaves every other benchmark's entry
    untouched, so running one benchmark alone never clobbers the others' recorded numbers.
    """
    data: dict[str, Any] = {}
    if _BASELINE_PATH.is_file():
        data = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    data[benchmark] = {
        "commit": _commit_sha(),
        "environment": _environment(),
        "measurements": measurements,
    }
    _BASELINE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
