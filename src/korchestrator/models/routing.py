"""Contract layer. Imports: stdlib, pydantic.

The custom-router contract: the externalised ``ModelCard``, the ``TaskSemantics`` a router may
consider, the ``RoutingContext`` passed to ``select_model``, and the explainable ``RoutingResult``.
Frozen and ``extra="forbid"``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ModelCard",
    "RoutingContext",
    "RoutingResult",
    "TaskSemantics",
]


class ModelCard(BaseModel):
    """Externalised capability/cost/latency description of one model."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    name: str
    provider: str
    description: str
    capabilities: tuple[str, ...] = ()
    context_window: int = Field(gt=0)
    cost_per_1k_input_usd: float = Field(ge=0.0)
    cost_per_1k_output_usd: float = Field(ge=0.0)
    latency_p50_ms: int = Field(ge=0)
    quality_score: float = Field(ge=0.0, le=1.0)
    fallbacks: tuple[str, ...] = ()


class TaskSemantics(BaseModel):
    """What the router knows about the task it must place."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: str
    difficulty: Literal["trivial", "moderate", "complex"]
    required_capabilities: tuple[str, ...] = ()
    estimated_input_tokens: int = Field(default=0, ge=0)
    estimated_output_tokens: int = Field(default=0, ge=0)
    embedding: tuple[float, ...] | None = None


class RoutingContext(BaseModel):
    """Everything a ``BaseRouter.select_model`` call is allowed to consider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    task: TaskSemantics
    candidates: tuple[ModelCard, ...] = ()
    explicit_model: str | None = None
    tenant_id: str = "default"


class RoutingResult(BaseModel):
    """The router's decision, always explainable."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_name: str
    strategy: Literal[
        "explicit", "semantic", "algorithmic", "composite", "user_function", "fallback"
    ]
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    fallbacks: tuple[str, ...] = ()
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
