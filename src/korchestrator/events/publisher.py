"""Events layer. Imports: types, exceptions, logging, stdlib, pydantic.

A transport-agnostic streaming publisher. The SDK **emits** events; it does not serve HTTP. A
consumer subscribes and iterates asynchronously — e.g. an application maps the stream to Server-Sent
Events with :func:`format_sse` and serves it itself. Publishing fans out to every subscriber's
bounded queue; a slow subscriber drops events rather than blocking the run.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.types import JSONValue

__all__ = ["Event", "EventPublisher", "Subscription", "format_sse"]

_logger = logging.getLogger("korchestrator.events")


class Event(BaseModel):
    """A single streamed event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    payload: Mapping[str, JSONValue] = Field(default_factory=dict)
    run_id: str | None = None


class EventPublisher:
    """Fan events out to asynchronous subscribers (no HTTP, no transport assumptions).

    Args:
        max_queue: Per-subscriber buffer. A subscriber that falls this far behind drops events.

    Example:
        >>> import asyncio
        >>> from korchestrator.events import Event, EventPublisher
        >>> async def demo():
        ...     publisher = EventPublisher()
        ...     sub = publisher.subscribe()
        ...     await publisher.publish(Event(name="superstep", payload={"n": 1}))
        ...     event = await sub.get()
        ...     sub.close()
        ...     return event.name
        >>> asyncio.run(demo())
        'superstep'
    """

    def __init__(self, *, max_queue: int = 1000) -> None:
        """Create a publisher with no subscribers and the given per-subscriber buffer size."""
        self._max_queue = max_queue
        self._subscribers: list[asyncio.Queue[Event]] = []

    async def publish(self, event: Event) -> None:
        """Deliver ``event`` to every subscriber, dropping it for any whose buffer is full."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                _logger.warning("events.subscriber_lagging", extra={"event": event.name})

    def subscribe(self) -> Subscription:
        """Register a new subscriber and return its :class:`Subscription`."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.append(queue)
        return Subscription(self, queue)

    def _remove(self, queue: asyncio.Queue[Event]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        """The number of active subscribers."""
        return len(self._subscribers)


class Subscription:
    """An async stream of :class:`Event`s for one subscriber.

    Iterate with ``async for`` or pull one at a time with :meth:`get`; call :meth:`close` (or use it
    as an async context manager) to unsubscribe.
    """

    def __init__(self, publisher: EventPublisher, queue: asyncio.Queue[Event]) -> None:
        """Bind the subscription to its publisher and buffer."""
        self._publisher = publisher
        self._queue = queue

    async def get(self) -> Event:
        """Await and return the next event."""
        return await self._queue.get()

    def __aiter__(self) -> Subscription:
        """Return ``self`` — the subscription is its own async iterator."""
        return self

    async def __anext__(self) -> Event:
        """Await the next event for ``async for`` iteration."""
        return await self._queue.get()

    def close(self) -> None:
        """Unsubscribe; the publisher stops delivering to this subscription."""
        self._publisher._remove(self._queue)

    async def __aenter__(self) -> Subscription:
        """Enter the subscription as an async context manager."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close the subscription on context exit."""
        self.close()


def format_sse(event: Event) -> str:
    r"""Render ``event`` as a Server-Sent Events frame (the caller serves it; the SDK does not).

    Example:
        >>> from korchestrator.events import Event, format_sse
        >>> format_sse(Event(name="superstep", payload={"n": 1}))
        'event: superstep\ndata: {"n": 1}\n\n'
    """
    data = json.dumps(dict(event.payload), sort_keys=True, separators=(", ", ": "))
    return f"event: {event.name}\ndata: {data}\n\n"
