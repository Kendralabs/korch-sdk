"""Façade layer (composition root). Imports: config, interfaces, models, agents, taxonomy, services.

The Tier-1 ``Korch`` entry point: run an objective with one line. This is the composition root —
the one place collaborators are wired. ``run`` classifies the objective (taxonomy), plans a team of
agents (the Architect), and drives the plan through the kernel and runtime to a ``RunResult``.
Reasoning requires the ``[dspy]`` extra (ADR 0013); MockLM keeps it offline and key-free.
"""

from __future__ import annotations

import asyncio

from korchestrator.agents import ArchitectAgent
from korchestrator.config import Settings
from korchestrator.interfaces import (
    BaseRouter,
    GraphRepository,
    IDurableRuntime,
    IModelGateway,
)
from korchestrator.models.result import RunResult
from korchestrator.services import _composition as comp
from korchestrator.taxonomy import TaxonomyClassifier

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

        Classifies the objective, has the Architect plan a team of agents, and drives the plan
        through the kernel and the configured runtime.

        Args:
            objective: The goal, at least 10 characters.
            max_supersteps: Hard halt bound. Defaults to 10.

        Returns:
            The terminal :class:`RunResult`, including ``final_answer``.

        Raises:
            ValidationError: If ``objective`` is shorter than 10 characters.
            MissingExtraError: If reasoning is used without the ``[dspy]`` extra.

        Example:
            >>> from korchestrator import Korch
            >>> Korch().run("Summarize durable agent execution")  # doctest: +SKIP
        """
        comp.validate_objective(objective)
        settings = self._settings or Settings.from_env()
        gateway = comp.resolve_gateway(settings, self._model_gateway)
        clock = comp.wall_clock()

        async def _flow() -> RunResult:
            semantics = TaxonomyClassifier().classify(objective)
            plan = (
                await ArchitectAgent()
                .bind(gateway=gateway)
                .plan(
                    objective,
                    intent=semantics.intent,
                    difficulty=semantics.difficulty,
                    max_supersteps=max_supersteps,
                )
            )
            graph = comp.graph_from_configs(plan.agents, plan.edges, clock=clock, gateway=gateway)
            return await comp.run_graph(
                graph,
                settings=settings,
                clock=clock,
                objective=objective,
                max_supersteps=plan.max_supersteps,
            )

        return asyncio.run(_flow())
