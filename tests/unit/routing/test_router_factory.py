"""Unit tests for the get_router factory and its strategy chains (spec 11 §154, P5.2)."""

from __future__ import annotations

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError
from korchestrator.interfaces import BaseRouter
from korchestrator.models.routing import ModelCard, RoutingContext, TaskSemantics
from korchestrator.routing import get_router

_TASK = TaskSemantics(intent="summarize", difficulty="moderate")


def _card(name: str, *, cost: float, quality: float) -> ModelCard:
    return ModelCard(
        name=name,
        provider="p",
        description=f"{name} model",
        context_window=1000,
        cost_per_1k_input_usd=cost,
        cost_per_1k_output_usd=cost * 3,
        latency_p50_ms=500,
        quality_score=quality,
    )


def _ctx(*, agent_id: str = "w", explicit_model: str | None = None) -> RoutingContext:
    return RoutingContext(agent_id=agent_id, task=_TASK, explicit_model=explicit_model)


def test_default_router_is_a_base_router() -> None:
    assert isinstance(get_router(), BaseRouter)


async def test_default_chain_resolves_via_fallback() -> None:
    # Zero-config: nothing pinned, so the explicit strategy declines and the fallback tail resolves.
    result = await get_router().select_model(_ctx(agent_id="orphan"))
    assert result.strategy == "fallback"
    assert result.model_name


async def test_explicit_map_from_settings_picks_the_named_model() -> None:
    router = get_router(Settings(agent_model_map={"lead": "gpt-4o"}))
    result = await router.select_model(_ctx(agent_id="lead"))
    assert result.model_name == "gpt-4o"
    assert result.strategy == "explicit"


async def test_composite_strategy_uses_priority_order() -> None:
    router = get_router(
        Settings(routing_strategy="composite", routing_priority_order=("explicit", "fallback"))
    )
    result = await router.select_model(_ctx(explicit_model="gpt-4o"))
    assert result.model_name == "gpt-4o"


async def test_algorithmic_strategy_ranks_candidates() -> None:
    router = get_router(Settings(routing_strategy="algorithmic", routing_weights={"quality": 1.0}))
    ctx = RoutingContext(
        agent_id="w",
        task=_TASK,
        candidates=(
            _card("cheap", cost=0.0001, quality=0.7),
            _card("strong", cost=0.02, quality=0.99),
        ),
    )
    result = await router.select_model(ctx)
    assert result.model_name == "strong"  # explicit declines, algorithmic ranks by quality
    assert result.strategy == "algorithmic"


def test_unknown_strategy_name_in_priority_order_raises() -> None:
    with pytest.raises(ConfigurationError):
        get_router(
            Settings(routing_strategy="composite", routing_priority_order=("nonsense", "fallback"))
        )
