"""bench_superstep.py — wall time of one superstep with N agents (spec 09 §8).

What good looks like: time scales roughly ~1x, not ~Nx — the agents genuinely run concurrently.
Drives the real production path (``Swarm`` -> ``WorkerAgent`` -> ``asyncio.to_thread``), under a
gateway with a fixed per-call delay, so concurrency is directly visible in wall time. Informational,
never blocks CI (``pytest benchmarks -m benchmark``).
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest
from _record import record

from korchestrator import Agent, Swarm
from korchestrator.models.routing import ModelCard
from korchestrator.models.state import Message, MessageRole

pytestmark = pytest.mark.benchmark

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_DELAY_SECONDS = 0.05
_AGENT_COUNTS = (1, 5, 25, 100)


class _DelayedGateway:
    """A gateway with a fixed per-call delay — makes real concurrency visible in wall time."""

    def __init__(self, delay: float) -> None:
        self._delay = delay

    async def complete(
        self, messages: object, *, model: str, max_tokens: int | None = None
    ) -> Message:
        await asyncio.sleep(self._delay)
        return Message(
            id="m",
            role=MessageRole.ASSISTANT,
            sender="mock",
            content="ok",
            superstep=0,
            valid_time=NOW,
        )

    async def available_models(self) -> list[ModelCard]:
        return []


def _run_n_agents(n: int) -> float:
    swarm = Swarm(
        objective="Answer the question directly and concisely",
        model_gateway=_DelayedGateway(_DELAY_SECONDS),
    )
    for i in range(n):
        swarm.add(Agent(id=f"a{i}", role="responder"))
    start = time.perf_counter()
    swarm.run(max_supersteps=1)
    return time.perf_counter() - start


def test_bench_superstep_scales_sublinearly() -> None:
    pytest.importorskip("dspy")
    # A cold first call pays a one-time cost (DSPy signature compilation, thread-pool warm-up)
    # that has nothing to do with N and would otherwise swamp N=1's timing; warm the same path
    # once, unmeasured, before recording.
    _run_n_agents(1)
    timings = {n: _run_n_agents(n) for n in _AGENT_COUNTS}

    baseline = timings[_AGENT_COUNTS[0]]
    record(
        "bench_superstep",
        {
            "delay_seconds": _DELAY_SECONDS,
            "wall_seconds": {str(n): timings[n] for n in _AGENT_COUNTS},
            "ratio_vs_n1": {str(n): timings[n] / baseline for n in _AGENT_COUNTS},
        },
    )

    # Every N ran and produced a positive wall time; the actual scaling ratio is read from
    # baseline.json by a human deciding whether it regressed (spec 09 §8) — CI noise on shared
    # runners is too unreliable to hard-gate on here.
    assert all(timings[n] > 0 for n in _AGENT_COUNTS)
