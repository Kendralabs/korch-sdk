"""Cognitive layer (L2). Imports: interfaces, models, exceptions, stdlib.

The algorithmic routing strategy: rank candidate :class:`ModelCard`s by a weighted blend of quality,
cost, and latency, after filtering to those that cover the task's required capabilities. Pure and
deterministic — the same context always yields the same ranking, with a stable tie-break by model
name — so routing stays replay-safe.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from korchestrator.constants import error_codes as codes
from korchestrator.exceptions import RoutingError
from korchestrator.models.routing import ModelCard, RoutingContext, RoutingResult

__all__ = ["AlgorithmicRouter"]

_DIMENSIONS = ("quality", "cost", "latency")


class AlgorithmicRouter:
    """Rank candidates by a weighted quality / cost / latency score.

    Cost and latency are inverted (cheaper and faster score higher) and every dimension is
    normalised across the candidate set to ``[0, 1]``, so the weights (``ROUTING_WEIGHTS``) trade
    them off directly. Candidates that lack a required capability are dropped before ranking.

    Args:
        weights: Weight per dimension over ``"quality"``, ``"cost"``, ``"latency"``. Missing keys
            count as ``0``; a non-positive total falls back to equal weights.

    Example:
        >>> import asyncio
        >>> from korchestrator.models.routing import ModelCard, RoutingContext, TaskSemantics
        >>> from korchestrator.routing.algorithmic import AlgorithmicRouter
        >>> cheap = ModelCard(
        ...     name="mini", provider="p", description="d", context_window=1000,
        ...     cost_per_1k_input_usd=0.0001, cost_per_1k_output_usd=0.0002,
        ...     latency_p50_ms=300, quality_score=0.7,
        ... )
        >>> strong = ModelCard(
        ...     name="max", provider="p", description="d", context_window=1000,
        ...     cost_per_1k_input_usd=0.01, cost_per_1k_output_usd=0.03,
        ...     latency_p50_ms=900, quality_score=0.95,
        ... )
        >>> ctx = RoutingContext(
        ...     agent_id="w",
        ...     task=TaskSemantics(intent="general", difficulty="trivial"),
        ...     candidates=(cheap, strong),
        ... )
        >>> asyncio.run(AlgorithmicRouter({"cost": 1.0}).select_model(ctx)).model_name
        'mini'
    """

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        """Normalise the weights, falling back to equal weighting on a non-positive total."""
        raw = {dim: float(weights.get(dim, 0.0)) for dim in _DIMENSIONS} if weights else {}
        total = sum(raw.values())
        if total <= 0.0:
            self._weights = {dim: 1.0 / len(_DIMENSIONS) for dim in _DIMENSIONS}
        else:
            self._weights = {dim: value / total for dim, value in raw.items()}

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        """Rank the eligible candidates and return the top-scoring model."""
        eligible = _eligible(context.candidates, context.task.required_capabilities)
        if not eligible:
            raise RoutingError(
                f"No candidate model covers the required capabilities "
                f"{context.task.required_capabilities} for agent {context.agent_id!r}. Widen the "
                "candidate set (MODELCARD_SOURCE) or relax the required capabilities.",
                code=codes.ROUTING_NO_CANDIDATES,
            )
        scored = sorted(
            ((self._score(card, eligible), card.name, card) for card in eligible),
            key=lambda item: (-item[0], item[1]),  # highest score, then name for a stable tie-break
        )
        score, _, best = scored[0]
        return RoutingResult(
            model_name=best.name,
            strategy="algorithmic",
            score=round(score, 6),
            reason=(
                f"ranked {len(eligible)} candidate(s) by weighted quality/cost/latency; "
                f"{best.name!r} scored {score:.3f}"
            ),
            fallbacks=best.fallbacks,
            estimated_cost_usd=_estimate_cost(best, context),
        )

    def _score(self, card: ModelCard, candidates: Sequence[ModelCard]) -> float:
        norms = {
            "quality": card.quality_score,
            "cost": _inverse_norm(
                card.cost_per_1k_input_usd, [c.cost_per_1k_input_usd for c in candidates]
            ),
            "latency": _inverse_norm(card.latency_p50_ms, [c.latency_p50_ms for c in candidates]),
        }
        return sum(self._weights[dim] * norms[dim] for dim in _DIMENSIONS)


def _eligible(candidates: Sequence[ModelCard], required: Sequence[str]) -> tuple[ModelCard, ...]:
    if not required:
        return tuple(candidates)
    needed = set(required)
    return tuple(card for card in candidates if needed <= set(card.capabilities))


def _inverse_norm(value: float, values: Sequence[float]) -> float:
    """Normalise ``value`` into ``[0, 1]`` where a *lower* raw value scores *higher*."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return 1.0
    return (hi - value) / (hi - lo)


def _estimate_cost(card: ModelCard, context: RoutingContext) -> float:
    task = context.task
    return round(
        (task.estimated_input_tokens / 1000.0) * card.cost_per_1k_input_usd
        + (task.estimated_output_tokens / 1000.0) * card.cost_per_1k_output_usd,
        6,
    )
