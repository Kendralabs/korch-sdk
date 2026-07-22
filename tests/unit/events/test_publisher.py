"""Unit tests for the event publisher and SSE formatting (P6.7)."""

from __future__ import annotations

from korchestrator.events import Event, EventPublisher, format_sse


async def test_publish_reaches_a_subscriber() -> None:
    publisher = EventPublisher()
    sub = publisher.subscribe()
    await publisher.publish(Event(name="superstep", payload={"n": 1}))
    event = await sub.get()
    assert event.name == "superstep"
    assert event.payload == {"n": 1}


async def test_fan_out_to_multiple_subscribers() -> None:
    publisher = EventPublisher()
    a, b = publisher.subscribe(), publisher.subscribe()
    await publisher.publish(Event(name="message"))
    assert (await a.get()).name == "message"
    assert (await b.get()).name == "message"


async def test_close_unsubscribes() -> None:
    publisher = EventPublisher()
    sub = publisher.subscribe()
    assert publisher.subscriber_count == 1
    sub.close()
    assert publisher.subscriber_count == 0


async def test_lagging_subscriber_drops_events_not_the_run() -> None:
    publisher = EventPublisher(max_queue=1)
    sub = publisher.subscribe()
    await publisher.publish(Event(name="a"))
    await publisher.publish(Event(name="b"))  # queue full -> dropped, no error
    assert (await sub.get()).name == "a"


async def test_async_iteration() -> None:
    publisher = EventPublisher()
    sub = publisher.subscribe()
    await publisher.publish(Event(name="one"))
    async for event in sub:
        assert event.name == "one"
        break


def test_format_sse_frame() -> None:
    frame = format_sse(Event(name="superstep", payload={"n": 1}))
    assert frame == 'event: superstep\ndata: {"n": 1}\n\n'
