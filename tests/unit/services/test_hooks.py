"""Unit tests for the middleware/hook framework: ordering and error isolation (P6.8, spec 07 §9)."""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.events import Event, EventPublisher
from korchestrator.models.state import AgentState
from korchestrator.services import HookRegistry, Middleware

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _state() -> AgentState:
    return AgentState(run_id="r1", objective="summarize the report", transaction_time=NOW)


class _Recorder(Middleware):
    def __init__(self, tag: str, log: list[str]) -> None:
        self._tag = tag
        self._log = log

    async def before_superstep(self, state: AgentState) -> None:
        self._log.append(f"before:{self._tag}")

    async def after_superstep(self, state: AgentState) -> None:
        self._log.append(f"after:{self._tag}")


async def test_before_in_order_after_in_reverse() -> None:
    log: list[str] = []
    registry = (
        HookRegistry()
        .register_middleware(_Recorder("a", log))
        .register_middleware(_Recorder("b", log))
    )
    await registry.before_superstep(_state())
    await registry.after_superstep(_state())
    # before_* registration order, after_* reverse (stack nesting).
    assert log == ["before:a", "before:b", "after:b", "after:a"]


async def test_middleware_runs_before_event_hooks() -> None:
    log: list[str] = []

    class M(Middleware):
        async def after_superstep(self, state: AgentState) -> None:
            log.append("middleware")

    registry = HookRegistry().register_middleware(M()).on("superstep", lambda e: log.append("hook"))
    await registry.after_superstep(_state())
    assert log == ["middleware", "hook"]


async def test_event_handlers_run_in_registration_order() -> None:
    log: list[str] = []
    registry = (
        HookRegistry()
        .on("message", lambda e: log.append("first"))
        .on("message", lambda e: log.append("second"))
    )
    await registry.dispatch(Event(name="message"))
    assert log == ["first", "second"]


async def test_a_raising_handler_is_isolated() -> None:
    log: list[str] = []

    def boom(event: Event) -> None:
        raise RuntimeError("handler down")

    registry = HookRegistry().on("x", boom).on("x", lambda e: log.append("survived"))
    await registry.dispatch(Event(name="x"))  # does not raise
    assert log == ["survived"]  # the second handler still ran


async def test_a_raising_middleware_is_isolated() -> None:
    log: list[str] = []

    class Boom(Middleware):
        async def before_superstep(self, state: AgentState) -> None:
            raise RuntimeError("middleware down")

    registry = HookRegistry().register_middleware(Boom()).register_middleware(_Recorder("ok", log))
    await registry.before_superstep(_state())  # does not raise
    assert log == ["before:ok"]


async def test_async_handlers_are_awaited() -> None:
    log: list[str] = []

    async def handler(event: Event) -> None:
        log.append(event.name)

    await HookRegistry().on("e", handler).dispatch(Event(name="e"))
    assert log == ["e"]


async def test_dispatched_events_mirror_to_a_publisher() -> None:
    publisher = EventPublisher()
    sub = publisher.subscribe()
    await HookRegistry(publisher=publisher).dispatch(Event(name="superstep"))
    assert (await sub.get()).name == "superstep"
