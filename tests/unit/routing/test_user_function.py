"""Unit tests for the user-function router and resolve_router (spec 07 §5, P5.5/P5.6)."""

from __future__ import annotations

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import RoutingError
from korchestrator.interfaces import BaseRouter
from korchestrator.models.routing import RoutingContext, RoutingResult, TaskSemantics
from korchestrator.routing import UserFunctionRouter, get_router, resolve_router

_CTX = RoutingContext(agent_id="w", task=TaskSemantics(intent="general", difficulty="trivial"))


def _pin(model: str) -> RoutingResult:
    return RoutingResult(model_name=model, strategy="user_function", score=1.0, reason="pinned")


async def test_sync_function_is_adapted() -> None:
    router = UserFunctionRouter(lambda context: _pin("mini"))
    result = await router.select_model(_CTX)
    assert result.model_name == "mini"


async def test_async_function_is_awaited() -> None:
    async def choose(context: RoutingContext) -> RoutingResult:
        return _pin("async-model")

    result = await UserFunctionRouter(choose).select_model(_CTX)
    assert result.model_name == "async-model"


async def test_wrong_return_type_raises_routing_error() -> None:
    router = UserFunctionRouter(lambda context: "gpt-4o")  # type: ignore[arg-type,return-value]
    with pytest.raises(RoutingError):
        await router.select_model(_CTX)


def test_resolve_router_returns_the_injected_router() -> None:
    # A custom BaseRouter plugs in with no package edit (P5.6 acceptance).
    custom = UserFunctionRouter(lambda context: _pin("x"))
    assert resolve_router(Settings(), router=custom) is custom


def test_resolve_router_builds_from_settings_when_none_injected() -> None:
    router = resolve_router(Settings())
    assert isinstance(router, BaseRouter)
    assert router is not get_router  # a built instance, not the factory
