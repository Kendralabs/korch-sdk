"""Façade layer (composition root). Imports: config, interfaces, models, agents, services.

The typed ``Swarm`` builder (Tier 2): declare an explicit agent topology fluently, then run it.
``run`` binds each agent's clock and gateway, builds the kernel graph from the declared topology,
and drives it through the configured runtime. Reasoning requires the ``[dspy]`` extra (ADR 0013).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from typing_extensions import Self

from korchestrator.agents import Agent
from korchestrator.config import Settings
from korchestrator.interfaces import (
    BaseRouter,
    GraphRepository,
    IDurableRuntime,
    IModelGateway,
)
from korchestrator.models.result import RunResult
from korchestrator.services import _composition as comp
from korchestrator.services.hooks import EventHandler, Middleware

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
        middleware: Middleware fired around each superstep, in registration order.

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
        middleware: Sequence[Middleware] = (),
    ) -> None:
        """Start an empty swarm for ``objective``; store optionally injected collaborators."""
        self._objective = objective
        self._settings = settings
        self._model_gateway = model_gateway
        self._runtime = runtime
        self._router = router
        self._repository = repository
        self._middleware = tuple(middleware)
        self._handlers: list[tuple[str, EventHandler]] = []
        self._agents: dict[str, Agent] = {}
        self._edges: list[tuple[str, str]] = []

    def add(self, agent: Agent) -> Self:
        """Add an agent to the swarm and return ``self`` for chaining."""
        self._agents[agent.id] = agent
        return self

    def on(self, event: str, handler: EventHandler) -> Self:
        """Register ``handler`` for ``event`` (e.g. ``"superstep"``); returns ``self``."""
        self._handlers.append((event, handler))
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
        """Run the swarm's declared topology to a terminal :class:`RunResult`.

        Args:
            max_supersteps: Hard halt bound. Defaults to 10.

        Returns:
            The terminal :class:`RunResult`, including ``final_answer``.

        Raises:
            ValidationError: If the objective is too short or the topology is invalid (no agents,
                or an edge referencing an unknown agent).
            MissingExtraError: If reasoning is used without the ``[dspy]`` extra.

        Example:
            >>> from korchestrator import Agent, Swarm
            >>> swarm = Swarm(objective="Summarize the design").add(Agent(id="lead", role="lead"))
            >>> swarm.run(max_supersteps=5)  # doctest: +SKIP
        """
        comp.validate_objective(self._objective)
        settings = self._settings or Settings.from_env()
        gateway = comp.resolve_gateway(settings, self._model_gateway)
        clock = comp.wall_clock()
        agents = tuple(self._agents.values())

        async def _flow() -> RunResult:
            semantics = comp.classify(self._objective)
            router, candidates = comp.resolve_routing(settings, self._router)
            graph = await comp.graph_from_agents(
                agents,
                self._edges,
                clock=clock,
                gateway=gateway,
                router=router,
                task=semantics,
                candidates=candidates,
            )
            return await comp.run_graph(
                graph,
                settings=settings,
                clock=clock,
                objective=self._objective,
                max_supersteps=max_supersteps,
                observer=comp.build_observer(self._middleware, self._handlers),
            )

        return asyncio.run(_flow())
