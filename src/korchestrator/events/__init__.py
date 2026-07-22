"""Integration layer.

Allowed imports (beyond stdlib + pydantic): models, types, exceptions, logging. Publishes
transport-agnostic execution events; the SDK emits, it does not serve HTTP.
"""

from korchestrator.events.publisher import Event, EventPublisher, Subscription, format_sse

__all__ = ["Event", "EventPublisher", "Subscription", "format_sse"]
