"""Unit tests for the benchmark-regression comparator (spec 09 §8, P10.6).

Reuses ``scripts.check_benchmark_regression.compare`` — the same comparison the standalone CI step
runs — so there is one canonical implementation, not two that could drift apart.
"""

from __future__ import annotations

from scripts.check_benchmark_regression import compare


def _baseline(**overrides: object) -> dict[str, object]:
    data = {
        "bench_import": {"measurements": {"korchestrator_cumulative_us": 1_000_000}},
        "bench_superstep": {"measurements": {"ratio_vs_n1": {"100": 10.0}}},
        "bench_telemetry_overhead": {"measurements": {"off_vs_bare_ratio": 1.2}},
    }
    data.update(overrides)
    return data


def test_identical_baselines_produce_no_warnings() -> None:
    before = _baseline()
    after = _baseline()
    assert compare(before, after) == []


def test_a_small_change_within_the_threshold_produces_no_warning() -> None:
    before = _baseline()
    after = _baseline(
        bench_import={"measurements": {"korchestrator_cumulative_us": 1_200_000}}  # 1.2x
    )
    assert compare(before, after) == []


def test_a_regression_past_the_threshold_is_reported() -> None:
    before = _baseline()
    after = _baseline(
        bench_import={"measurements": {"korchestrator_cumulative_us": 2_000_000}}  # 2x
    )
    warnings = compare(before, after)
    assert len(warnings) == 1
    assert "bench_import.korchestrator_cumulative_us" in warnings[0]
    assert "2.00x worse" in warnings[0]


def test_a_nested_metric_regression_is_reported_by_its_full_path() -> None:
    before = _baseline()
    after = _baseline(bench_superstep={"measurements": {"ratio_vs_n1": {"100": 20.0}}})  # 2x
    warnings = compare(before, after)
    assert len(warnings) == 1
    assert "bench_superstep.ratio_vs_n1.100" in warnings[0]


def test_a_missing_benchmark_in_either_side_is_skipped_not_crashed() -> None:
    before = _baseline()
    after = {k: v for k, v in _baseline().items() if k != "bench_import"}
    assert compare(before, after) == []


def test_multiple_regressions_are_all_reported() -> None:
    before = _baseline()
    after = _baseline(
        bench_import={"measurements": {"korchestrator_cumulative_us": 2_000_000}},
        bench_telemetry_overhead={"measurements": {"off_vs_bare_ratio": 3.0}},
    )
    warnings = compare(before, after)
    assert len(warnings) == 2
