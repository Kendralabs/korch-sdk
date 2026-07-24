# Streaming a run's events

The SDK **emits** events as a run progresses; it does not serve them over HTTP itself — that's
your application's job (see `format_sse` below). This tutorial wires a swarm run's `"superstep"`
events into an `EventPublisher` and consumes them from a subscriber.

## The pieces

- **`.on(event, handler)`** registers a callback fired for a named event as a run executes. Today
  the kernel dispatches one built-in event, `"superstep"`, after each superstep completes.
- **`EventPublisher`/`Subscription`** is a transport-agnostic pub/sub primitive: `publish(event)`
  fans an event out to every open subscriber; `Subscription.get()` (or `async for` over it) pulls
  events one at a time.
- **`format_sse(event)`** renders one `Event` as a Server-Sent Events frame — the shape an HTTP
  handler would write to a streaming response.

## Wiring them together

```python
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
print(result.status, result.supersteps)
```

`Swarm.run()` is a synchronous facade — it runs its own event loop internally and returns only once
the run is complete. `on_superstep` is called, and `publisher.publish(event)` runs, *inside* that
loop, once per superstep, while the run is in progress; by the time `swarm.run()` returns, every
event is already sitting in `subscription`'s buffer, waiting to be read.

## Draining the subscription

```python
async def drain(count: int) -> list[Event]:
    return [await subscription.get() for _ in range(count)]


events = asyncio.run(drain(result.supersteps))
subscription.close()

for event in events:
    print(event.payload["superstep"], event.payload["status"])
```

Each event's payload carries `superstep` (the just-completed superstep number — note it reports the
*post-increment* count, so the first event says `1`, not `0`) and `status`. `status` reports
`"running"` for every superstep, including the last — the run's terminal status (`"completed"`,
`"cancelled"`, etc.) is only known once every agent has halted, which happens *after* the last
`"superstep"` event fires; read `result.status` for the terminal outcome.

## Rendering as Server-Sent Events

```python
for event in events:
    print(format_sse(event), end="")
```

```text
event: superstep
data: {"status": "running", "superstep": 1}

event: superstep
data: {"status": "running", "superstep": 2}

```

This is exactly the byte shape an HTTP handler would `yield` for a `text/event-stream` response —
`format_sse` does the rendering, your application owns the transport (spec 07 §9: the SDK emits
events, it does not serve HTTP).

## A live pipeline, not a drain-after

The example above subscribes before the run and drains after, which keeps it simple and
deterministic for a tutorial. A real streaming server instead reads from `subscription` on a
**separate** task or thread concurrently with the run — e.g. an async generator consuming
`async for event in subscription` that a web framework streams to a client as each event arrives,
rather than waiting for the whole run to finish first.

## Next

- [Human-in-the-loop](hitl.md) — a run's events are the natural place to learn its `run_id` for
  `pause`/`resume`.
