"""Cognitive layer (L2). Imports: interfaces, models, exceptions, stdlib.

The default routing strategy and its always-succeeds tail. :class:`ExplicitRouter` honours a
pinned model — the per-context ``explicit_model`` or an ``agent_id → model`` map — and raises when
none is set, so a chain can move on. :class:`FallbackRouter` never raises: it returns a configured
default model, guaranteeing the zero-config install always resolves ("explicit plus one fallback is
the default", spec 11 §150).
"""

from __future__ import annotations

from collections.abc import Mapping

from korchestrator.constants import error_codes as codes
from korchestrator.exceptions import RoutingError
from korchestrator.models.routing import RoutingContext, RoutingResult

__all__ = ["DEFAULT_FALLBACK_MODEL", "ExplicitRouter", "FallbackRouter"]

# The model the fallback tail resolves to when nothing else decided. A cheap, general model; a
# real deployment overrides it via AGENT_MODEL_MAP or a ranking strategy.
DEFAULT_FALLBACK_MODEL = "gpt-4o-mini"


class ExplicitRouter:
    """Select the explicitly pinned model for an agent, or raise so a chain can fall through.

    Resolution order: the context's ``explicit_model`` (a model pinned on the agent), then the
    ``agent_id → model`` map (from ``AGENT_MODEL_MAP``). With neither set this router raises
    :class:`RoutingError`, letting a :class:`CompositeRouter` try the next strategy.

    Args:
        agent_model_map: Optional ``agent_id → model`` overrides.

    Example:
        >>> import asyncio
        >>> from korchestrator.models.routing import RoutingContext, TaskSemantics
        >>> from korchestrator.routing.explicit import ExplicitRouter
        >>> ctx = RoutingContext(
        ...     agent_id="lead",
        ...     task=TaskSemantics(intent="summarize", difficulty="moderate"),
        ...     explicit_model="gpt-4o",
        ... )
        >>> asyncio.run(ExplicitRouter().select_model(ctx)).model_name
        'gpt-4o'
    """

    def __init__(self, agent_model_map: Mapping[str, str] | None = None) -> None:
        """Store an immutable copy of the ``agent_id → model`` overrides."""
        self._map: dict[str, str] = dict(agent_model_map or {})

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        """Return the pinned model for ``context``, or raise :class:`RoutingError` if unset."""
        model = context.explicit_model or self._map.get(context.agent_id)
        if model is None:
            raise RoutingError(
                f"No explicit model for agent {context.agent_id!r}: neither a pinned model nor an "
                "AGENT_MODEL_MAP entry. Pin a model, add a map entry, or use a ranking strategy.",
                code=codes.ROUTING_NO_CANDIDATES,
            )
        source = "pinned on the agent" if context.explicit_model else "AGENT_MODEL_MAP"
        return RoutingResult(
            model_name=model,
            strategy="explicit",
            score=1.0,
            reason=f"explicit model {model!r} ({source})",
        )


class FallbackRouter:
    """Always resolve to a configured default model — the tail that never raises.

    This makes the default install resolvable without any candidates, extras, or configuration:
    when every prior strategy in a chain declines, the fallback returns its default model with an
    explanatory ``reason``.

    Args:
        default_model: The model to resolve to. Defaults to :data:`DEFAULT_FALLBACK_MODEL`.

    Example:
        >>> import asyncio
        >>> from korchestrator.models.routing import RoutingContext, TaskSemantics
        >>> from korchestrator.routing.explicit import FallbackRouter
        >>> ctx = RoutingContext(
        ...     agent_id="w", task=TaskSemantics(intent="general", difficulty="trivial")
        ... )
        >>> asyncio.run(FallbackRouter().select_model(ctx)).strategy
        'fallback'
    """

    def __init__(self, default_model: str = DEFAULT_FALLBACK_MODEL) -> None:
        """Store the default model this tail resolves to."""
        self._default = default_model

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        """Resolve to the default model, explaining that no earlier strategy decided."""
        return RoutingResult(
            model_name=self._default,
            strategy="fallback",
            score=0.5,
            reason=f"no strategy selected a model; used the default {self._default!r}",
        )
