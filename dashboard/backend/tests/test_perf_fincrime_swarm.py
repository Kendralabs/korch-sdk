"""Concurrency/performance test for the fincrime investigation swarm.

Fires N independent runs of the swarm concurrently, straight against `Swarm.run()` (bypassing
FastAPI/HTTP entirely, so the measurement is the SDK's own kernel/agent-orchestration cost, not
web-framework overhead), and reports per-run latency (p50/p95/mean) plus a success-rate assertion
— a real regression test, not just a benchmark script.

Offline by default (T1: no network/cost), each run building its own OfflineGateway/registry/swarm
(no shared mutable state across concurrent runs). The HITL gate is intentionally omitted here
(`_build_swarm(..., hitl=None)`) — it blocks on human approval, which has nothing to do with
kernel/orchestration throughput; the gate itself is covered by test_fincrime_router.py.

To measure real-OpenAI latency instead: set OPENAI_API_KEY before running (expect much higher
latency and real cost — this is not the default and CI never does this):
    OPENAI_API_KEY=sk-... PERF_CONCURRENCY=3 pytest tests/test_perf_fincrime_swarm.py -v -s
"""

import asyncio
import os
import statistics
import time

import pytest

from fincrime_router import _OBJECTIVE, _build_gateway, _build_swarm, _build_tool_registry

_CONCURRENCY = int(os.environ.get("PERF_CONCURRENCY", "5"))
_MIN_SUCCESS_RATE = 0.8  # allow headroom for the offline gateway's own inherent flakiness budget


async def _one_run(index: int) -> tuple[bool, float, str]:
    """Build and run one fully independent swarm instance; return (ok, seconds, status)."""
    gateway = _build_gateway(lambda name, payload: None)
    registry = _build_tool_registry()
    swarm = _build_swarm(_OBJECTIVE, {}, gateway, registry, hitl=None)

    started = time.monotonic()
    try:
        result = await asyncio.to_thread(swarm.run, max_supersteps=8)
        elapsed = time.monotonic() - started
        return result.status.value == "completed", elapsed, result.status.value
    except Exception as exc:  # a failed run is a data point, not a test crash
        elapsed = time.monotonic() - started
        return False, elapsed, f"error: {exc}"


_TRACING_KEYS = ("OPENAI_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "KCG_API_KEY")


def test_concurrent_fincrime_runs_meet_latency_and_success_targets() -> None:
    # Force the offline gateway *and* both tracing wrappers off, regardless of what's in the
    # environment/.env — this test's determinism/speed/cost guarantees (T1) must not depend on
    # whether OPENAI_API_KEY/LANGSMITH_API_KEY/KCG_API_KEY happen to be set. TracedGateway and
    # KCGTracedGateway each make a real HTTP call per LLM turn when their key is present, which
    # blew this test's latency budget the moment KCG_API_KEY landed in .env (p95 67s vs a 20s
    # budget) — the exact class of regression this assertion exists to catch. The live-model
    # variant below is the explicit opt-in path for a real key.
    saved = {k: os.environ.pop(k, None) for k in _TRACING_KEYS}
    try:

        async def _go() -> list[tuple[bool, float, str]]:
            return await asyncio.gather(*(_one_run(i) for i in range(_CONCURRENCY)))

        results = asyncio.run(asyncio.wait_for(_go(), timeout=120))
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    successes = [elapsed for ok, elapsed, _ in results if ok]
    failures = [(elapsed, status) for ok, elapsed, status in results if not ok]
    all_latencies = sorted(elapsed for _, elapsed, _ in results)

    success_rate = len(successes) / len(results)
    p50 = statistics.median(all_latencies)
    p95 = all_latencies[min(len(all_latencies) - 1, int(len(all_latencies) * 0.95))]
    mean = statistics.mean(all_latencies)

    print(
        f"\n[perf] concurrency={_CONCURRENCY} success_rate={success_rate:.0%} "
        f"p50={p50:.2f}s p95={p95:.2f}s mean={mean:.2f}s "
        f"failures={[status for _, status in failures]}",
        flush=True,
    )

    assert success_rate >= _MIN_SUCCESS_RATE, (
        f"success rate {success_rate:.0%} below {_MIN_SUCCESS_RATE:.0%} threshold; "
        f"failures: {failures}"
    )
    # Offline runs with no tool-call retries should stay fast even under concurrency; a
    # regression here (kernel contention, a new blocking call in the hot path, etc.) should
    # fail this rather than silently degrade.
    assert p95 < 20.0, f"p95 latency {p95:.2f}s exceeds the 20s budget for offline concurrent runs"


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="live-model perf run: set OPENAI_API_KEY to opt in"
)
def test_concurrent_fincrime_runs_live_openai() -> None:
    """Same measurement against real OpenAI — opt-in only, not part of the default suite."""

    async def _go() -> list[tuple[bool, float, str]]:
        return await asyncio.gather(*(_one_run(i) for i in range(_CONCURRENCY)))

    results = asyncio.run(asyncio.wait_for(_go(), timeout=180))
    successes = [elapsed for ok, elapsed, _ in results if ok]
    print(
        f"\n[perf-live] concurrency={_CONCURRENCY} success_rate={len(successes) / len(results):.0%} "
        f"latencies={[round(elapsed, 1) for _, elapsed, _ in results]}",
        flush=True,
    )
    assert len(successes) >= 1, "no live run succeeded"
