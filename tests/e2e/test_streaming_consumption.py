"""E2E: a full local swarm run's dispatched events are consumable as a real event stream (P10.3).

``HookRegistry``'s dispatch/publish mechanics and ``EventPublisher``/``Subscription``/``format_sse``
are each unit-tested in isolation (``tests/unit/services/test_hooks.py``,
``tests/unit/events/test_publisher.py``). This file's job is the "streaming consumption" leg of
P10.3's E2E checklist (spec 12): proving a **real, multi-superstep swarm run**'s events arrive at
a subscriber in order and render as valid SSE frames — the same shape an application would serve
to an HTTP client (spec 07 §9: the SDK emits events, it does not serve HTTP).
"""

from __future__ import annotations

import asyncio

import pytest

from korchestrator import Agent, Swarm
from korchestrator.events import Event, EventPublisher, format_sse
from korchestrator.models.state import RunStatus
from korchestrator.providers import MockLM


def test_a_full_swarm_runs_streaming_events_consumption() -> None:
    """A three-agent run's ``superstep`` events, dispatched to a real ``EventPublisher``,
    arrive at a subscriber in strictly increasing superstep order and each renders as a valid
    SSE frame — proving the local run -> hook dispatch -> publisher -> subscriber -> SSE path is
    wired together end to end, not just each piece unit-tested alone.
    """
    pytest.importorskip("dspy")
    publisher = EventPublisher()
    # publish() runs inside Swarm.run()'s own event loop; subscribing before the run starts and
    # draining the queue afterward (rather than concurrently) keeps the test deterministic (T2) —
    # the events are already sitting in the subscriber's queue once the run returns.
    subscription = publisher.subscribe()
    received: list[Event] = []

    async def on_superstep(event: Event) -> None:
        await publisher.publish(event)

    swarm = (
        Swarm(objective="Review this change for security and performance", model_gateway=MockLM())
        .add(Agent(id="security", role="security-reviewer"))
        .add(Agent(id="perf", role="performance-reviewer"))
        .add(Agent(id="lead", role="review-lead"))
        .edges([("security", "lead"), ("perf", "lead")])
        .on("superstep", on_superstep)
    )
    result = swarm.run(max_supersteps=5)
    assert result.status is RunStatus.COMPLETED

    async def drain(count: int) -> None:
        for _ in range(count):
            received.append(await subscription.get())

    asyncio.run(drain(result.supersteps))
    subscription.close()

    assert len(received) == result.supersteps
    # after_superstep fires with the post-increment state, so the first event reports superstep 1.
    assert [event.payload["superstep"] for event in received] == list(
        range(1, result.supersteps + 1)
    )
    assert all(event.run_id == result.run_id for event in received)
    frames = [format_sse(event) for event in received]
    assert all(frame.startswith("event: superstep\ndata: {") for frame in frames)
    assert all(frame.endswith("\n\n") for frame in frames)
