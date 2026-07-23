"""bench_serde.py — serialize/deserialize throughput for AgentState (spec 09 §8).

What good looks like: no order-of-magnitude regression across releases. Informational, never
blocks CI (``pytest benchmarks -m benchmark``).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from _record import record

from korchestrator.models.state import AgentState, Message, MessageRole
from korchestrator.serializers import from_json, to_json

pytestmark = pytest.mark.benchmark

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_SIZES = (1, 50, 500)
_ITERATIONS = 200


def _state_with_messages(count: int) -> AgentState:
    messages = tuple(
        Message(
            id=f"m{i}",
            sender=f"agent{i % 5}",
            content=f"message body number {i} with some representative prose content",
            kind="thought" if i % 3 else "answer",
            role=MessageRole.ASSISTANT,
            superstep=i // 10,
            valid_time=NOW,
        )
        for i in range(count)
    )
    return AgentState(
        run_id="bench-run",
        objective="summarize the quarterly incident reports in detail",
        messages=messages,
        transaction_time=NOW,
    )


def _throughput(state: AgentState, *, iterations: int) -> dict[str, float]:
    start = time.perf_counter()
    for _ in range(iterations):
        payload = to_json(state)
    serialize_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        from_json(payload, AgentState)
    deserialize_elapsed = time.perf_counter() - start

    return {
        "serialize_ops_per_sec": iterations / serialize_elapsed,
        "deserialize_ops_per_sec": iterations / deserialize_elapsed,
        "payload_bytes": len(payload.encode("utf-8")),
    }


def test_bench_serde_throughput() -> None:
    measurements = {
        f"{size}_messages": _throughput(_state_with_messages(size), iterations=_ITERATIONS)
        for size in _SIZES
    }
    record("bench_serde", measurements)

    # Round-trip correctness is already locked by the serializers' own unit tests; this benchmark
    # only asserts the pipeline produced a result for every size, not a throughput threshold.
    assert set(measurements) == {f"{size}_messages" for size in _SIZES}
