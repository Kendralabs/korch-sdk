"""Streaming a run's events out to a subscriber, rendered as Server-Sent Events frames.

Run: python examples/07_streaming.py
Requires: pip install "korchestrator[dspy]"
"""

import asyncio

from korchestrator import Agent, Swarm
from korchestrator.events import Event, EventPublisher, format_sse
from korchestrator.providers import MockLM

publisher = EventPublisher()
subscription = publisher.subscribe()


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
print("status:", result.status, "supersteps:", result.supersteps)


async def drain(count: int) -> list[Event]:
    return [await subscription.get() for _ in range(count)]


events = asyncio.run(drain(result.supersteps))
subscription.close()

for event in events:
    print(format_sse(event), end="")

assert len(events) == result.supersteps
