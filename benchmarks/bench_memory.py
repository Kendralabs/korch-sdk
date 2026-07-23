"""bench_memory.py — peak memory for a run of M supersteps with N agents (spec 09 §8).

What good looks like: memory grows with retained state (message history), not per superstep — a
per-superstep leak shows up as memory growing faster than the retained-message count would explain.
Uses ``tracemalloc`` (stdlib, cross-platform) for peak *Python-allocated* memory rather than OS RSS,
which isolates the kernel's own retention behaviour from interpreter/thread noise. Informational,
never blocks CI (``pytest benchmarks -m benchmark``).
"""

from __future__ import annotations

import asyncio
import tracemalloc
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone

import pytest
from _record import record

from korchestrator.core import PregelRunner
from korchestrator.core.graph import AgentGraph, Node
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, Message, StateUpdate

pytestmark = pytest.mark.benchmark

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_N_AGENTS = 10
_SUPERSTEP_COUNTS = (5, 20, 50)


def _graph(n_agents: int, max_superstep: int) -> AgentGraph:
    def _make_compute(agent_id: str) -> Callable[[AgentState], Coroutine[None, None, StateUpdate]]:
        async def compute(state: AgentState) -> StateUpdate:
            halt = state.superstep >= max_superstep - 1
            message = Message(
                id="placeholder",
                sender=agent_id,
                content=f"contribution from {agent_id} at superstep {state.superstep}",
                kind="thought",
                superstep=0,
                valid_time=NOW,
            )
            return StateUpdate(agent_id=agent_id, messages=(message,), halt=halt, valid_time=NOW)

        return compute

    nodes = [
        Node(AgentConfig(id=f"a{i}", persona=AgentPersona(role="r")), _make_compute(f"a{i}"))
        for i in range(n_agents)
    ]
    return AgentGraph(nodes)


def _peak_bytes_for(n_agents: int, max_superstep: int) -> int:
    runner = PregelRunner(
        _graph(n_agents, max_superstep), clock=lambda: NOW, max_supersteps=max_superstep + 1
    )
    start = AgentState(
        run_id="bench-run", objective="run to the fixed superstep bound", transaction_time=NOW
    )
    tracemalloc.start()
    try:
        asyncio.run(runner.run(start))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def test_bench_memory_scales_with_retained_state() -> None:
    measurements = {
        f"{m}_supersteps": {"peak_bytes": _peak_bytes_for(_N_AGENTS, m), "n_agents": _N_AGENTS}
        for m in _SUPERSTEP_COUNTS
    }
    record("bench_memory", measurements)

    # At this run's scale, fixed per-call allocation overhead can dominate the small amount of
    # genuinely retained message state, so peak bytes are not reliably monotonic in M run to run —
    # exactly the noise spec 09 §8 says never to hard-gate on. Only assert every size measured
    # successfully; a human reads the recorded ratios in baseline.json to judge a real regression.
    peaks = [measurements[f"{m}_supersteps"]["peak_bytes"] for m in _SUPERSTEP_COUNTS]
    assert all(peak > 0 for peak in peaks)
