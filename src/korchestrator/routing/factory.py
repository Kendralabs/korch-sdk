"""Cognitive layer (L2). Imports: config, interfaces, exceptions, routing (siblings within layer).

The routing composition point. :func:`get_router` turns a :class:`~korchestrator.config.Settings`
into a ready :class:`~korchestrator.interfaces.BaseRouter`: it builds the strategy chain named by
``ROUTING_STRATEGY`` (always ending in the never-declining fallback) and wraps it in a
:class:`~korchestrator.routing.composite.CompositeRouter`. Advanced strategies are built lazily so
the base install never needs the ``[routing]`` extra.
"""

from __future__ import annotations

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError
from korchestrator.interfaces import BaseRouter
from korchestrator.routing.algorithmic import AlgorithmicRouter
from korchestrator.routing.composite import CompositeRouter
from korchestrator.routing.explicit import ExplicitRouter, FallbackRouter
from korchestrator.routing.semantic import Embedder, SemanticRouter, make_embedder

__all__ = ["get_router", "resolve_router"]

_FALLBACK = "fallback"


def resolve_router(
    settings: Settings, *, router: BaseRouter | None = None, embedder: Embedder | None = None
) -> BaseRouter:
    """Return the injected router, or build one from ``settings`` — the composition entrypoint.

    An explicitly injected ``router`` (e.g. ``Korch(router=my_router)``) wins, so a custom
    :class:`~korchestrator.interfaces.BaseRouter` plugs in with no package edit. Otherwise the
    strategy is built from ``settings`` via :func:`get_router`.

    Args:
        settings: Configuration selecting the strategy when no router is injected.
        router: An explicit router to use as-is.
        embedder: An embedding backend forwarded to :func:`get_router` for the semantic strategy.

    Returns:
        The router to use for this run.

    Example:
        >>> from korchestrator.config import Settings
        >>> from korchestrator.routing import resolve_router
        >>> hasattr(resolve_router(Settings()), "select_model")
        True
    """
    if router is not None:
        return router
    return get_router(settings, embedder=embedder)


# The strategy chain each ROUTING_STRATEGY expands to (composite uses ROUTING_PRIORITY_ORDER). An
# explicitly pinned model is always honoured first, then the named strategy, then the fallback tail.
_FIXED_CHAINS: dict[str, tuple[str, ...]] = {
    "explicit": ("explicit", _FALLBACK),
    "algorithmic": ("explicit", "algorithmic", _FALLBACK),
    "semantic": ("explicit", "semantic", _FALLBACK),
}


def get_router(settings: Settings | None = None, *, embedder: Embedder | None = None) -> BaseRouter:
    """Build the router for ``settings`` — a composite chain ending in the fallback tail.

    The default (``ROUTING_STRATEGY="explicit"``) resolves to explicit → fallback and needs no
    extra. ``"algorithmic"`` and ``"semantic"`` insert their strategy before the tail; semantic
    needs the ``[routing]`` extra. ``"composite"`` builds the chain from ``ROUTING_PRIORITY_ORDER``.

    Args:
        settings: Configuration selecting the strategy and its inputs. Defaults to :class:`Settings`
            (the zero-config explicit strategy).
        embedder: An embedding backend for the semantic strategy. When omitted, one is built from
            ``settings`` (requiring the ``[routing]`` extra); inject a fake to test semantic routing
            offline.

    Returns:
        A :class:`~korchestrator.interfaces.BaseRouter` ready for ``select_model``.

    Raises:
        ConfigurationError: If a strategy name in the chain is not recognised.
        MissingExtraError: If a semantic strategy is selected without the ``[routing]`` extra.

    Example:
        >>> from korchestrator.routing import get_router
        >>> router = get_router()  # zero-config: explicit → fallback
        >>> hasattr(router, "select_model")
        True
    """
    settings = settings or Settings()
    chain = [
        _build_router(name, settings, embedder)
        for name in _chain_for(settings.routing_strategy, settings)
    ]
    return CompositeRouter(chain)


def _chain_for(strategy: str, settings: Settings) -> tuple[str, ...]:
    if strategy == "composite":
        order = settings.routing_priority_order
        return order if _FALLBACK in order else (*order, _FALLBACK)
    return _FIXED_CHAINS[strategy]


def _build_router(name: str, settings: Settings, embedder: Embedder | None) -> BaseRouter:
    if name == "explicit":
        return ExplicitRouter(settings.agent_model_map)
    if name == "algorithmic":
        return AlgorithmicRouter(settings.routing_weights)
    if name == "semantic":
        return SemanticRouter(
            embedder or make_embedder(settings),
            ttl_seconds=settings.modelcard_cache_ttl_seconds,
        )
    if name == _FALLBACK:
        return FallbackRouter()
    raise ConfigurationError(
        f"Unknown routing strategy {name!r}. Valid strategies: explicit, algorithmic, semantic, "
        "fallback. Fix ROUTING_STRATEGY or ROUTING_PRIORITY_ORDER."
    )
