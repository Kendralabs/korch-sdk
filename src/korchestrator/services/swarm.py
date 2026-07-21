"""Façade layer (composition root). Imports: korchestrator.config, interfaces, models, services.

The typed ``Swarm`` builder (Tier 2): declare an explicit agent topology fluently, then run it.
Building is functional; execution (``run``) is wired to the kernel in P4.9.
"""

from __future__ import annotations

from typing_extensions import Self

from korchestrator.config import Settings
from korchestrator.interfaces import (
    BaseRouter,
    GraphRepository,
    IDurableRuntime,
    IModelGateway,
)
from korchestrator.models.result import RunResult
from korchestrator.services.agent import Agent

__all__ = ["Swarm"]


class Swarm:
    """A typed, explicitly constructed agent swarm.

    Build the topology with :meth:`add` and :meth:`edges` (both return ``Self`` so chaining
    type-checks), then :meth:`run` it. Collaborators are optional and resolved from ``Settings``
    at the composition root when omitted.

    Args:
        objective: The goal, at least 10 characters.
        settings: Explicit settings; resolved from the environment when omitted.
        model_gateway: The gateway to inject; resolved from config when omitted.
        runtime: The durable runtime to inject; resolved from config when omitted.
        router: The model router to inject; resolved from config when omitted.
        repository: The graph repository to inject; resolved from config when omitted.

    Example:
        >>> from korchestrator import Agent, Swarm
        >>> swarm = (
        ...     Swarm(objective="Review this PR for security and performance")
        ...     .add(Agent(id="security", role="security-reviewer"))
        ...     .add(Agent(id="lead", role="review-lead"))
        ...     .edges([("security", "lead")])
        ... )
        >>> swarm.size
        2
    """

    def __init__(
        self,
        objective: str,
        *,
        settings: Settings | None = None,
        model_gateway: IModelGateway | None = None,
        runtime: IDurableRuntime | None = None,
        router: BaseRouter | None = None,
        repository: GraphRepository | None = None,
    ) -> None:
        """Start an empty swarm for ``objective``; store optionally injected collaborators."""
        self._objective = objective
        self._settings = settings
        self._model_gateway = model_gateway
        self._runtime = runtime
        self._router = router
        self._repository = repository
        self._agents: dict[str, Agent] = {}
        self._edges: list[tuple[str, str]] = []

    def add(self, agent: Agent) -> Self:
        """Add an agent to the swarm and return ``self`` for chaining."""
        self._agents[agent.id] = agent
        return self

    def edges(self, edges: list[tuple[str, str]]) -> Self:
        """Declare directed edges ``(from_id, to_id)`` and return ``self`` for chaining."""
        self._edges.extend(edges)
        return self

    @property
    def size(self) -> int:
        """The number of agents added to the swarm."""
        return len(self._agents)

    def run(self, *, max_supersteps: int = 10) -> RunResult:
        """Run the swarm to a terminal :class:`RunResult`.

        Raises:
            NotImplementedError: Until the kernel is wired in P4.9.

        Example:
            >>> from korchestrator import Agent, Swarm
            >>> swarm = Swarm(objective="Summarize the design").add(Agent(id="lead", role="lead"))
            >>> swarm.run(max_supersteps=5)  # doctest: +SKIP
        """
        raise NotImplementedError("Swarm.run is wired to the kernel in P4.9.")
