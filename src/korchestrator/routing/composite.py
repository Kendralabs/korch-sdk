"""Cognitive layer (L2). Imports: interfaces, models, exceptions, stdlib, logging.

Strategy composition. :class:`CompositeRouter` tries its sub-routers in order and returns the
first decision, realising the documented fallback chain (e.g. explicit → algorithmic → fallback).
A sub-router that declines raises :class:`RoutingError`; the composite moves on. The winning
:class:`RoutingResult` passes through unchanged so its ``strategy`` and ``reason`` name the router
that actually decided.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence

from korchestrator.constants import error_codes as codes
from korchestrator.exceptions import ConfigurationError, RoutingError
from korchestrator.interfaces import BaseRouter
from korchestrator.models.routing import RoutingContext, RoutingResult

__all__ = ["CompositeRouter", "UserFunctionRouter"]

_logger = logging.getLogger("korchestrator.routing")

# A user routing function: sync or async, context in, decision out.
RouterFunction = Callable[[RoutingContext], "RoutingResult | Awaitable[RoutingResult]"]


class CompositeRouter:
    """Try sub-routers in order and return the first that selects a model.

    Args:
        routers: The ordered strategies to try. Must be non-empty. Put a router that never
            declines last (e.g. :class:`~korchestrator.routing.explicit.FallbackRouter`) so the
            chain always resolves.

    Raises:
        ConfigurationError: If ``routers`` is empty.

    Example:
        >>> import asyncio
        >>> from korchestrator.models.routing import RoutingContext, TaskSemantics
        >>> from korchestrator.routing.composite import CompositeRouter
        >>> from korchestrator.routing.explicit import ExplicitRouter, FallbackRouter
        >>> chain = CompositeRouter((ExplicitRouter(), FallbackRouter()))
        >>> ctx = RoutingContext(
        ...     agent_id="w", task=TaskSemantics(intent="general", difficulty="trivial")
        ... )
        >>> asyncio.run(chain.select_model(ctx)).strategy  # explicit declines, fallback resolves
        'fallback'
    """

    def __init__(self, routers: Sequence[BaseRouter]) -> None:
        """Store the ordered chain, rejecting an empty one."""
        if not routers:
            raise ConfigurationError(
                "A CompositeRouter needs at least one sub-router. Configure ROUTING_PRIORITY_ORDER "
                "with at least one known strategy (it should end in 'fallback')."
            )
        self._routers: tuple[BaseRouter, ...] = tuple(routers)

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        """Return the first sub-router's decision; raise if every one declines."""
        for router in self._routers:
            try:
                return await router.select_model(context)
            except RoutingError as exc:
                _logger.debug(
                    "routing.strategy_declined",
                    extra={"agent_id": context.agent_id, "reason": exc.message},
                )
        raise RoutingError(
            f"No routing strategy selected a model for agent {context.agent_id!r}. Add a fallback "
            "to the chain, pin a model, or widen the candidate set.",
            code=codes.ROUTING_NO_CANDIDATES,
        )


class UserFunctionRouter:
    """Adapt a user-supplied callable into a :class:`~korchestrator.interfaces.BaseRouter`.

    The function receives the :class:`RoutingContext` and returns a :class:`RoutingResult`; it may
    be synchronous or a coroutine function. This is the lightest way to plug custom routing in
    without subclassing — ``Korch(router=UserFunctionRouter(my_fn))``. Keep it pure with respect to
    its input so routing stays replay-safe (spec 07 §5).

    Args:
        function: The routing callable, ``(RoutingContext) -> RoutingResult`` (sync or async).

    Example:
        >>> import asyncio
        >>> from korchestrator.models.routing import RoutingContext, RoutingResult, TaskSemantics
        >>> from korchestrator.routing.composite import UserFunctionRouter
        >>> def cheapest(context):
        ...     return RoutingResult(
        ...         model_name="mini", strategy="user_function", score=1.0, reason="always mini"
        ...     )
        >>> ctx = RoutingContext(
        ...     agent_id="w", task=TaskSemantics(intent="general", difficulty="trivial")
        ... )
        >>> asyncio.run(UserFunctionRouter(cheapest).select_model(ctx)).model_name
        'mini'
    """

    def __init__(self, function: RouterFunction) -> None:
        """Store the user's routing callable."""
        self._function = function

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        """Invoke the callable (awaiting it if async) and validate the result type."""
        outcome = self._function(context)
        result = await outcome if inspect.isawaitable(outcome) else outcome
        if not isinstance(result, RoutingResult):
            raise RoutingError(
                "A user routing function must return a RoutingResult, but it returned "
                f"{type(result).__name__}. Return RoutingResult(model_name=..., strategy=..., "
                "score=..., reason=...).",
                code=codes.KORCH_ROUTING_FAILED,
            )
        return result
