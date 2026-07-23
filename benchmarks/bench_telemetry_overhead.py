"""bench_telemetry_overhead.py — telemetry-on vs telemetry-off delta for a fixed swarm (spec 08 §4).

Spec 08 §4: "Zero overhead when off... A benchmark in ``benchmarks/`` MUST record the delta between
telemetry-on and telemetry-off for a fixed swarm and assert the off-path is within noise of a build
with the extra uninstalled." Unlike the other benchmarks, this one really does assert — it is the
one place spec 08 hard-requires it, not merely records for a human to read later.

Drives ``services._composition.run_graph`` directly (the function ``agent.run``'s span/metrics wrap)
against a synthetic, DSPy-free graph, so the measurement isolates telemetry's own overhead rather
than DSPy/thread-pool noise. There is no literal "extra uninstalled" build to compare against here
(uninstalling a package mid-benchmark is not practical); a bare ``PregelRunner.run`` with no
telemetry wrapping at all stands in for it — code-path identical to "off" in an extra-uninstalled
build, since the off-path never imports OTel either way (confirmed by inspection of ``start_span``/
``record_metric``: both return before any ``_otel()`` import when disabled).
"""

from __future__ import annotations

import asyncio
import statistics
import time
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone

import pytest
from _record import record

from korchestrator.config import Settings
from korchestrator.core import PregelRunner
from korchestrator.core.graph import AgentGraph, Node
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, Message, StateUpdate
from korchestrator.services import _composition as comp

pytestmark = pytest.mark.benchmark

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_N_AGENTS = 5
_MAX_SUPERSTEP = 5
_REPETITIONS = 25
# Generous — this isolates a real regression (an accidental eager cost on the off-path) from
# ordinary run-to-run noise on a small, fast, synthetic run (spec 09 §8: never over-tighten a
# benchmark tolerance against noise it cannot control).
_OFF_VS_BARE_TOLERANCE = 2.0


def _graph() -> AgentGraph:
    def _make_compute(agent_id: str) -> Callable[[AgentState], Coroutine[None, None, StateUpdate]]:
        async def compute(state: AgentState) -> StateUpdate:
            halt = state.superstep >= _MAX_SUPERSTEP - 1
            message = Message(
                id="placeholder",
                sender=agent_id,
                content=f"contribution from {agent_id}",
                kind="thought",
                superstep=0,
                valid_time=NOW,
            )
            return StateUpdate(agent_id=agent_id, messages=(message,), halt=halt, valid_time=NOW)

        return compute

    nodes = [
        Node(AgentConfig(id=f"a{i}", persona=AgentPersona(role="r")), _make_compute(f"a{i}"))
        for i in range(_N_AGENTS)
    ]
    return AgentGraph(nodes)


def _bare_run() -> float:
    """No telemetry wrapping at all — the "extra uninstalled" proxy."""
    runner = PregelRunner(_graph(), clock=lambda: NOW, max_supersteps=_MAX_SUPERSTEP + 1)
    state = AgentState(
        run_id="bench-run", objective="run to the fixed superstep bound", transaction_time=NOW
    )
    start = time.perf_counter()
    asyncio.run(runner.run(state))
    return time.perf_counter() - start


def _run_graph_with_telemetry(*, enabled: bool) -> float:
    settings = Settings(korch_telemetry_enabled=enabled)
    start = time.perf_counter()
    asyncio.run(
        comp.run_graph(
            _graph(),
            settings=settings,
            clock=lambda: NOW,
            objective="run to the fixed superstep bound",
            max_supersteps=_MAX_SUPERSTEP + 1,
        )
    )
    return time.perf_counter() - start


def test_bench_telemetry_off_path_stays_within_noise_of_no_telemetry() -> None:
    bare = statistics.median(_bare_run() for _ in range(_REPETITIONS))
    off = statistics.median(_run_graph_with_telemetry(enabled=False) for _ in range(_REPETITIONS))
    on = statistics.median(_run_graph_with_telemetry(enabled=True) for _ in range(_REPETITIONS))

    record(
        "bench_telemetry_overhead",
        {
            "repetitions": _REPETITIONS,
            "bare_seconds": bare,
            "off_seconds": off,
            "on_seconds": on,
            "off_vs_bare_ratio": off / bare,
            "on_vs_off_ratio": on / off,
        },
    )

    # The spec 08 §4 hard requirement: telemetry disabled must cost within noise of no telemetry
    # code running at all.
    assert off <= bare * _OFF_VS_BARE_TOLERANCE
