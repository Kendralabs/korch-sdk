"""Contract tests for models/routing.py (P1.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.models.routing import (
    ModelCard,
    RoutingContext,
    RoutingResult,
    TaskSemantics,
)


def _card(**overrides: object) -> ModelCard:
    base: dict[str, object] = {
        "name": "gpt-4o-mini",
        "provider": "openai",
        "description": "small fast model",
        "context_window": 128000,
        "cost_per_1k_input_usd": 0.15,
        "cost_per_1k_output_usd": 0.60,
        "latency_p50_ms": 400,
        "quality_score": 0.7,
    }
    base.update(overrides)
    return ModelCard(**base)  # type: ignore[arg-type]


def test_model_card_valid_and_named_model_field() -> None:
    card = _card()
    assert card.name == "gpt-4o-mini"
    assert card.fallbacks == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context_window", 0),
        ("cost_per_1k_input_usd", -0.1),
        ("latency_p50_ms", -1),
        ("quality_score", 1.1),
    ],
)
def test_model_card_bounds(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        _card(**{field: value})


def test_task_semantics_defaults_and_difficulty() -> None:
    task = TaskSemantics(intent="qa", difficulty="trivial")
    assert task.required_capabilities == ()
    assert task.estimated_input_tokens == 0
    assert task.embedding is None
    with pytest.raises(ValidationError):
        TaskSemantics(intent="qa", difficulty="hard")  # type: ignore[arg-type]


def test_routing_context_construction() -> None:
    ctx = RoutingContext(
        agent_id="lead",
        task=TaskSemantics(intent="qa", difficulty="moderate"),
        candidates=(_card(),),
    )
    assert ctx.tenant_id == "default"
    assert ctx.explicit_model is None


def test_routing_result_valid() -> None:
    result = RoutingResult(
        model_name="gpt-4o-mini", strategy="explicit", score=1.0, reason="mapped by AGENT_MODEL_MAP"
    )
    assert result.estimated_cost_usd == 0.0
    assert result.fallbacks == ()


def test_routing_result_strategy_is_constrained() -> None:
    with pytest.raises(ValidationError):
        RoutingResult(
            model_name="x",
            strategy="magic",  # type: ignore[arg-type]
            score=0.5,
            reason="?",
        )


def test_routing_result_score_bounds() -> None:
    with pytest.raises(ValidationError):
        RoutingResult(model_name="x", strategy="fallback", score=1.5, reason="?")
