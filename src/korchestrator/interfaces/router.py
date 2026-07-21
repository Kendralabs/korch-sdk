"""Contract layer. Imports: korchestrator.models, stdlib.

The ``BaseRouter`` supporting protocol — select a model for a task through a strategy.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from korchestrator.models.routing import RoutingContext, RoutingResult

__all__ = ["BaseRouter"]


@runtime_checkable
class BaseRouter(Protocol):
    """Select a model for a task and return an explainable decision.

    Implementations (strategies behind one factory, ``get_router()``): explicit (the default,
    works with no extra), algorithmic, semantic (``[routing]``), composite, and a user-supplied
    function. A custom router plugs in via config with no package edit.

    Concurrency: ``select_model`` MUST be safe to call concurrently and MUST be pure with respect
    to its :class:`RoutingContext` input — the same context yields the same
    :class:`RoutingResult`, so routing cannot introduce nondeterminism into a superstep.
    """

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        """Choose a model for ``context`` and return the decision with its rationale."""
        ...
