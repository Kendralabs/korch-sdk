"""Unit tests for the composite fallback chain (spec 07 §5, P5.2/P5.5)."""

from __future__ import annotations

import pytest

from korchestrator.exceptions import ConfigurationError, RoutingError
from korchestrator.models.routing import RoutingContext, TaskSemantics
from korchestrator.routing.composite import CompositeRouter
from korchestrator.routing.explicit import ExplicitRouter, FallbackRouter

_TASK = TaskSemantics(intent="summarize", difficulty="moderate")


def _ctx(*, agent_id: str = "w", explicit_model: str | None = None) -> RoutingContext:
    return RoutingContext(agent_id=agent_id, task=_TASK, explicit_model=explicit_model)


async def test_first_successful_strategy_wins() -> None:
    chain = CompositeRouter((ExplicitRouter(), FallbackRouter()))
    result = await chain.select_model(_ctx(explicit_model="gpt-4o"))
    assert result.model_name == "gpt-4o"
    assert result.strategy == "explicit"  # the winner's strategy passes through, not "composite"


async def test_chain_falls_through_to_the_tail() -> None:
    chain = CompositeRouter((ExplicitRouter(), FallbackRouter()))
    result = await chain.select_model(_ctx(agent_id="orphan"))
    assert result.strategy == "fallback"


async def test_empty_chain_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        CompositeRouter(())


async def test_chain_with_no_tail_can_decline() -> None:
    # Two explicit routers, neither resolving and no fallback: the composite raises.
    chain = CompositeRouter((ExplicitRouter(), ExplicitRouter()))
    with pytest.raises(RoutingError) as info:
        await chain.select_model(_ctx(agent_id="orphan"))
    assert info.value.code == "ROUTING_NO_CANDIDATES"
