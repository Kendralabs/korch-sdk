#!/usr/bin/env python3
"""Compare a fresh benchmark run against the committed baseline (spec 09 §8, P10.6).

Benchmarks are informational and never block CI — this script always exits ``0``. Its job is only
to surface a regression loudly (stdout, and a GitHub Actions ``::warning::`` annotation when run in
that environment) so a human can triage it as a defect, per spec 09 §8: "A performance regression is
triaged as a defect, not as a broken build, because benchmark numbers on shared CI runners are too
noisy to gate on."

Usage: run the benchmark suite (which overwrites ``benchmarks/baseline.json`` with fresh numbers)
against a saved copy of the **previously committed** baseline, then run this script:

    cp benchmarks/baseline.json /tmp/baseline.before.json
    pytest benchmarks -m benchmark
    python scripts/check_benchmark_regression.py /tmp/baseline.before.json benchmarks/baseline.json

The freshly-measured ``benchmarks/baseline.json`` is never committed back automatically — updating
the committed baseline is "a deliberate PR that explains the change" (spec 09 §8), a human decision,
not something CI does on its own.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# A regression this large is worth a human's attention; small run-to-run jitter on shared CI
# runners is expected and explicitly not something to chase (spec 09 §8).
_REGRESSION_THRESHOLD = 1.5

# Benchmark -> (path to the numeric leaf, higher-is-worse). Keeps the comparison to the one number
# per benchmark that most directly answers "did this get worse," rather than diffing every nested
# field (throughput fields are lower-is-worse and are handled by inverting the ratio).
_WATCHED: dict[str, tuple[tuple[str, ...], bool]] = {
    "bench_import": (("korchestrator_cumulative_us",), True),
    "bench_superstep": (("ratio_vs_n1", "100"), True),
    "bench_telemetry_overhead": (("off_vs_bare_ratio",), True),
}


def _dig(data: dict[str, Any], path: tuple[str, ...]) -> float | None:
    node: Any = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return float(node) if isinstance(node, int | float) else None


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return one warning line per benchmark whose watched metric regressed past the threshold."""
    warnings: list[str] = []
    for benchmark, (path, higher_is_worse) in _WATCHED.items():
        before_value = _dig(before.get(benchmark, {}).get("measurements", {}), path)
        after_value = _dig(after.get(benchmark, {}).get("measurements", {}), path)
        if before_value is None or after_value is None or before_value <= 0:
            continue
        ratio = after_value / before_value if higher_is_worse else before_value / after_value
        if ratio >= _REGRESSION_THRESHOLD:
            metric = ".".join(path)
            warnings.append(
                f"{benchmark}.{metric}: {before_value:.4g} -> {after_value:.4g} "
                f"({ratio:.2f}x worse)"
            )
    return warnings


def main(argv: list[str]) -> int:
    """Compare two baseline.json files given as argv[1] (before) and argv[2] (after)."""
    if len(argv) != 3:
        print(f"usage: {argv[0]} <before.json> <after.json>", file=sys.stderr)
        return 0
    before = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    after = json.loads(Path(argv[2]).read_text(encoding="utf-8"))

    warnings = compare(before, after)
    if not warnings:
        print("benchmark-regression: no watched metric regressed past the threshold")
        return 0

    for warning in warnings:
        print(f"POSSIBLE REGRESSION: {warning}")
        print(f"::warning::benchmark regression — {warning}")
    return 0  # informational only — never fails the build (spec 09 §8)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
