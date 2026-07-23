"""bench_import.py — import cost of ``import korchestrator`` (spec 09 §8).

What good looks like: import cost stays flat as the package grows; a step change means a new eager
dependency snuck into the top-level import graph (violating B5 — heavy deps like ``dspy``/
``temporalio``/``httpx`` must import lazily, inside the function that needs them). Informational,
never blocks CI (``pytest benchmarks -m benchmark``).
"""

from __future__ import annotations

import re
import subprocess
import sys

import pytest
from _record import record

pytestmark = pytest.mark.benchmark

_HEAVY_MODULES = ("dspy", "temporalio", "httpx", "opentelemetry", "mcp", "sentence_transformers")
# `-X importtime` writes one line per import to stderr:
#   import time:      123 |       456 | some.module
_LINE = re.compile(r"^import time:\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.+)$")


def test_bench_import_time() -> None:
    proc = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "import korchestrator"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    rows = [m.groups() for line in proc.stderr.splitlines() if (m := _LINE.match(line))]
    by_module = {name.strip(): int(cumulative) for _self, cumulative, name in rows}

    korchestrator_us = by_module.get("korchestrator", 0)
    heavy_present = sorted(
        name
        for name in by_module
        if any(name == heavy or name.startswith(f"{heavy}.") for heavy in _HEAVY_MODULES)
    )

    record(
        "bench_import",
        {
            "korchestrator_cumulative_us": korchestrator_us,
            "total_imports": len(rows),
            "heavy_modules_eagerly_imported": heavy_present,
        },
    )

    # The one thing this benchmark actually gates on locally, even though it never blocks CI: a
    # heavy optional dependency must never be pulled in by a bare `import korchestrator` (B5).
    assert not heavy_present, (
        f"import korchestrator eagerly pulled in heavy module(s): {heavy_present} — "
        "these must be imported lazily, inside the function that needs them (B5)."
    )
