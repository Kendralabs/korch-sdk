"""Unit tests for the explicit and fallback routers (spec 07 §5, P5.2)."""

from __future__ import annotations

import pytest

from korchestrator.exceptions import RoutingError
from korchestrator.models.routing import RoutingContext, TaskSemantics
from korchestrator.routing.explicit import DEFAULT_FALLBACK_MODEL, ExplicitRouter, FallbackRouter

_TASK = TaskSemantics(intent="summarize", difficulty="moderate")


def _ctx(*, agent_id: str = "w", explicit_model: str | None = None) -> RoutingContext:
    return RoutingContext(agent_id=agent_id, task=_TASK, explicit_model=explicit_model)


async def test_explicit_honours_pinned_model() -> None:
    result = await ExplicitRouter().select_model(_ctx(explicit_model="gpt-4o"))
    assert result.model_name == "gpt-4o"
    assert result.strategy == "explicit"
    assert result.score == 1.0


async def test_explicit_honours_agent_model_map() -> None:
    router = ExplicitRouter({"lead": "claude-3.5-sonnet"})
    result = await router.select_model(_ctx(agent_id="lead"))
    assert result.model_name == "claude-3.5-sonnet"


async def test_pinned_model_beats_the_map() -> None:
    router = ExplicitRouter({"lead": "gpt-4o-mini"})
    result = await router.select_model(_ctx(agent_id="lead", explicit_model="gpt-4o"))
    assert result.model_name == "gpt-4o"


async def test_explicit_declines_when_nothing_pinned() -> None:
    with pytest.raises(RoutingError) as info:
        await ExplicitRouter().select_model(_ctx(agent_id="orphan"))
    assert info.value.code == "ROUTING_NO_CANDIDATES"


async def test_explicit_is_pure() -> None:
    # Purity: same context yields the same decision, so routing stays replay-safe (spec 07 §5).
    router = ExplicitRouter({"lead": "gpt-4o"})
    first = await router.select_model(_ctx(agent_id="lead"))
    second = await router.select_model(_ctx(agent_id="lead"))
    assert first == second


async def test_fallback_always_resolves() -> None:
    result = await FallbackRouter().select_model(_ctx(agent_id="orphan"))
    assert result.model_name == DEFAULT_FALLBACK_MODEL
    assert result.strategy == "fallback"


async def test_fallback_honours_a_custom_default() -> None:
    result = await FallbackRouter("my-model").select_model(_ctx())
    assert result.model_name == "my-model"
