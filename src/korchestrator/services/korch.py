"""Façade layer (composition root). Imports: korchestrator.config, interfaces, models.

The Tier-1 ``Korch`` entry point: run an objective with one line. This is the composition root —
the one place collaborators are wired. Execution (``run``) is wired to the kernel in P4.9.
"""

from __future__ import annotations

from korchestrator.config import Settings
from korchestrator.interfaces import (
    BaseRouter,
    GraphRepository,
    IDurableRuntime,
    IModelGateway,
)
from korchestrator.models.result import RunResult

__all__ = ["Korch"]


class Korch:
    """The one-liner entry point to durable multi-agent execution.

    Constructing ``Korch`` wires the object graph: each collaborator is taken as given, or resolved
    from ``Settings`` once, here. With no arguments and no environment it runs locally with MockLM,
    the in-process runtime, and in-memory persistence.

    Args:
        settings: Explicit settings; resolved from the environment when omitted.
        model_gateway: The gateway to inject; resolved from config when omitted.
        runtime: The durable runtime to inject; resolved from config when omitted.
        router: The model router to inject; resolved from config when omitted.
        repository: The graph repository to inject; resolved from config when omitted.

    Example:
        >>> from korchestrator import Korch
        >>> korch = Korch()
        >>> korch.run("Summarize durable agent execution")  # doctest: +SKIP
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        model_gateway: IModelGateway | None = None,
        runtime: IDurableRuntime | None = None,
        router: BaseRouter | None = None,
        repository: GraphRepository | None = None,
    ) -> None:
        """Store the (optionally injected) collaborators; resolution happens on first use."""
        self._settings = settings
        self._model_gateway = model_gateway
        self._runtime = runtime
        self._router = router
        self._repository = repository

    def run(self, objective: str, *, max_supersteps: int = 10) -> RunResult:
        """Run a swarm against ``objective`` and return the terminal :class:`RunResult`.

        Args:
            objective: The goal, at least 10 characters.
            max_supersteps: Hard halt bound. Defaults to 10.

        Returns:
            The terminal :class:`RunResult`, including ``final_answer``.

        Raises:
            NotImplementedError: Until the kernel is wired in P4.9.

        Example:
            >>> from korchestrator import Korch
            >>> Korch().run("Summarize durable agent execution")  # doctest: +SKIP
        """
        raise NotImplementedError("Korch.run is wired to the kernel in P4.9.")
