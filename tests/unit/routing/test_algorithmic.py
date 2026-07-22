"""Unit tests for the algorithmic router (spec 11 §189, P5.3)."""

from __future__ import annotations

import pytest

from korchestrator.exceptions import RoutingError
from korchestrator.models.routing import ModelCard, RoutingContext, TaskSemantics
from korchestrator.routing.algorithmic import AlgorithmicRouter


def _card(
    name: str, *, cost: float, latency: int, quality: float, caps: tuple[str, ...] = ()
) -> ModelCard:
    return ModelCard(
        name=name,
        provider="p",
        description=f"{name} model",
        capabilities=caps,
        context_window=100_000,
        cost_per_1k_input_usd=cost,
        cost_per_1k_output_usd=cost * 3,
        latency_p50_ms=latency,
        quality_score=quality,
    )


_CHEAP = _card("cheap", cost=0.0001, latency=300, quality=0.70)
_STRONG = _card("strong", cost=0.01, latency=900, quality=0.95)


def _ctx(
    candidates: tuple[ModelCard, ...],
    *,
    required: tuple[str, ...] = (),
    in_tokens: int = 0,
    out_tokens: int = 0,
) -> RoutingContext:
    return RoutingContext(
        agent_id="w",
        task=TaskSemantics(
            intent="general",
            difficulty="moderate",
            required_capabilities=required,
            estimated_input_tokens=in_tokens,
            estimated_output_tokens=out_tokens,
        ),
        candidates=candidates,
    )


async def test_cost_weight_prefers_the_cheaper_model() -> None:
    router = AlgorithmicRouter({"cost": 1.0})
    result = await router.select_model(_ctx((_CHEAP, _STRONG)))
    assert result.model_name == "cheap"
    assert result.strategy == "algorithmic"


async def test_quality_weight_prefers_the_stronger_model() -> None:
    router = AlgorithmicRouter({"quality": 1.0})
    result = await router.select_model(_ctx((_CHEAP, _STRONG)))
    assert result.model_name == "strong"


async def test_score_is_bounded_and_cost_is_estimated() -> None:
    router = AlgorithmicRouter()  # default balanced weights
    result = await router.select_model(_ctx((_CHEAP, _STRONG), in_tokens=1000, out_tokens=500))
    assert 0.0 <= result.score <= 1.0
    assert result.estimated_cost_usd > 0.0


async def test_capability_filter_drops_ineligible_candidates() -> None:
    coder = _card("coder", cost=0.005, latency=500, quality=0.8, caps=("code-generation",))
    writer = _card("writer", cost=0.001, latency=400, quality=0.75, caps=("writing",))
    router = AlgorithmicRouter({"cost": 1.0})  # writer is cheaper, but lacks the capability
    result = await router.select_model(_ctx((coder, writer), required=("code-generation",)))
    assert result.model_name == "coder"


async def test_no_candidates_raises() -> None:
    with pytest.raises(RoutingError) as info:
        await AlgorithmicRouter().select_model(_ctx(()))
    assert info.value.code == "ROUTING_NO_CANDIDATES"


async def test_no_capable_candidate_raises() -> None:
    with pytest.raises(RoutingError):
        await AlgorithmicRouter().select_model(_ctx((_CHEAP,), required=("code-generation",)))


async def test_ranking_is_deterministic() -> None:
    router = AlgorithmicRouter({"quality": 0.5, "cost": 0.3, "latency": 0.2})
    first = await router.select_model(_ctx((_CHEAP, _STRONG)))
    second = await router.select_model(_ctx((_STRONG, _CHEAP)))  # order flipped
    assert first == second  # order-independent, stable tie-break
