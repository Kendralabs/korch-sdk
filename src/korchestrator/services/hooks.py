"""Façade layer. Imports: core, events, models, logging, stdlib.

The extension framework: :class:`Middleware` (wraps a phase, may observe) and :class:`HookRegistry`
(observes events). The registry implements the kernel's :class:`SuperstepObserver`, so the runtime
fires it around each superstep. Ordering and error isolation follow spec 07 §9:

* ``before_*`` middleware runs in registration order; ``after_*`` in **reverse** (stack nesting).
* Middleware runs before event hooks for the same phase; event handlers run in registration order.
* A raising hook or ``after_superstep`` middleware is caught, logged, and the run continues — a hook
  can never fail a run. (The ``before_superstep`` ``GovernanceHaltError`` veto → pause is wired with
  governance in a later phase; for now every failure is isolated so runs always complete.)

Hooks run in activity/in-process scope, never Temporal workflow scope, and MUST NOT mutate state.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Awaitable, Callable

from typing_extensions import Self

from korchestrator.events.publisher import Event, EventPublisher
from korchestrator.models.state import AgentState

__all__ = ["EventHandler", "HookRegistry", "Middleware"]

_logger = logging.getLogger("korchestrator.events")

# An event handler: receives the Event, sync or async; it must not raise (errors are isolated).
EventHandler = Callable[[Event], "Awaitable[None] | None"]


class Middleware:
    """Wrap a superstep or tool phase. Override the phases you care about; the rest are no-ops.

    Supported phases: ``before_superstep`` / ``after_superstep`` (fired around each barrier) and
    ``before_tool`` / ``after_tool`` (fired around a tool call once the agent tool-loop lands). A
    hook MUST NOT mutate ``state``; the barrier result is already computed when ``after_superstep``
    runs.

    Example:
        >>> from korchestrator.services import Middleware
        >>> class Counter(Middleware):
        ...     def __init__(self):
        ...         self.seen = 0
        ...     async def after_superstep(self, state):
        ...         self.seen += 1
    """

    async def before_superstep(self, state: AgentState) -> None:
        """Fired with the state about to be computed."""

    async def after_superstep(self, state: AgentState) -> None:
        """Fired with the state produced by the barrier."""

    async def before_tool(self, tool: str, args: object) -> None:
        """Fired before a tool call (dispatched when the agent tool-loop lands)."""

    async def after_tool(self, tool: str, result: object) -> None:
        """Fired after a tool call (dispatched when the agent tool-loop lands)."""


class HookRegistry:
    """Register middleware and event handlers; dispatch them with the documented order + isolation.

    Implements :class:`~korchestrator.core.pregel.SuperstepObserver`, so a runtime can drive it
    around each superstep. Optionally forwards every dispatched event to an :class:`EventPublisher`
    stream.

    Args:
        publisher: Optional stream to also publish dispatched events to.

    Example:
        >>> import asyncio
        >>> from datetime import datetime, timezone
        >>> from korchestrator.models.state import AgentState
        >>> from korchestrator.services.hooks import HookRegistry
        >>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        >>> fired = []
        >>> registry = HookRegistry().on("superstep", lambda event: fired.append(event.name))
        >>> state = AgentState(run_id="r", objective="summarize the report", transaction_time=now)
        >>> asyncio.run(registry.after_superstep(state))
        >>> fired
        ['superstep']
    """

    def __init__(self, *, publisher: EventPublisher | None = None) -> None:
        """Start with no middleware or handlers, optionally mirroring events to ``publisher``."""
        self._middleware: list[Middleware] = []
        self._handlers: dict[str, list[EventHandler]] = {}
        self._publisher = publisher

    def register_middleware(self, middleware: Middleware) -> Self:
        """Append ``middleware`` to the chain; return ``self`` for chaining."""
        self._middleware.append(middleware)
        return self

    def on(self, event: str, handler: EventHandler) -> Self:
        """Register ``handler`` for ``event`` (e.g. ``"superstep"``/``"message"``); returns self."""
        self._handlers.setdefault(event, []).append(handler)
        return self

    async def before_superstep(self, state: AgentState) -> None:
        """Run each middleware's ``before_superstep`` in registration order (errors isolated)."""
        for middleware in self._middleware:
            await self._safe(
                functools.partial(middleware.before_superstep, state), _name(middleware)
            )

    async def after_superstep(self, state: AgentState) -> None:
        """Run ``after_superstep`` in reverse order, then fire the ``superstep`` event."""
        for middleware in reversed(self._middleware):
            await self._safe(
                functools.partial(middleware.after_superstep, state), _name(middleware)
            )
        await self.dispatch(
            Event(
                name="superstep",
                payload={"superstep": state.superstep, "status": state.status.value},
                run_id=state.run_id,
            )
        )

    async def dispatch(self, event: Event) -> None:
        """Fire handlers for ``event.name`` in order, then publish (errors isolated)."""
        for handler in self._handlers.get(event.name, []):
            await self._safe(functools.partial(handler, event), _name(handler))
        if self._publisher is not None:
            await self._publisher.publish(event)

    async def _safe(self, call: Callable[[], object], who: str) -> None:
        try:
            result = call()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            # A hook or middleware can never fail a run: catch, log, and continue (spec 07 §9).
            _logger.error("hook.failed", extra={"handler": who, "error": str(exc)})


def _name(obj: object) -> str:
    return str(getattr(obj, "__qualname__", type(obj).__qualname__))
