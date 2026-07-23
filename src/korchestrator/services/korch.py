"""Façade layer (composition root). Imports: config, interfaces, models, agents, taxonomy, services.

The Tier-1 ``Korch`` entry point: run an objective with one line. This is the composition root —
the one place collaborators are wired. ``run`` classifies the objective (taxonomy), plans a team of
agents (the Architect), and drives the plan through the kernel and runtime to a ``RunResult``.
Reasoning requires the ``[dspy]`` extra (ADR 0013); MockLM keeps it offline and key-free.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence

from typing_extensions import Self

from korchestrator.agents import ArchitectAgent
from korchestrator.config import Settings
from korchestrator.interfaces import (
    BaseRouter,
    Connector,
    GraphRepository,
    IDurableRuntime,
    IModelGateway,
)
from korchestrator.models.result import RunResult
from korchestrator.services import _composition as comp
from korchestrator.services.hooks import EventHandler, Middleware
from korchestrator.tools import ConnectorRegistry
from korchestrator.types import JSONValue

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
        middleware: Middleware fired around each superstep, in registration order.
        connectors: Tools available to the Architect's plan (ADR 0015) — a
            :class:`~korchestrator.tools.ConnectorRegistry` this ``Korch`` owns, or connectors to
            build one from. Omit entirely if no agent needs tools; an agent whose planned
            ``AgentConfig.tools`` is non-empty with no ``connectors`` given raises
            ``ConfigurationError`` (P10.2).

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
        middleware: Sequence[Middleware] = (),
        connectors: Sequence[Connector] | ConnectorRegistry | None = None,
    ) -> None:
        """Store the (optionally injected) collaborators; resolution happens on first use."""
        self._settings = settings
        self._model_gateway = model_gateway
        self._runtime = runtime
        self._router = router
        self._repository = repository
        self._middleware = tuple(middleware)
        self._connectors = connectors
        self._handlers: list[tuple[str, EventHandler]] = []

    def on(self, event: str, handler: EventHandler) -> Self:
        """Register ``handler`` for ``event`` (e.g. ``"superstep"``); returns ``self``."""
        self._handlers.append((event, handler))
        return self

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
            ValidationError: If ``objective`` is shorter than 10 characters, or ``max_supersteps``
                is outside 1-100.
            MissingExtraError: If reasoning is used without the ``[dspy]`` extra.

        Example:
            >>> from korchestrator import Korch
            >>> Korch().run("Summarize durable agent execution")  # doctest: +SKIP
        """
        comp.validate_objective(objective)
        comp.validate_max_supersteps(max_supersteps)
        settings = self._settings or Settings.from_env()
        gateway = comp.resolve_gateway(settings, self._model_gateway)
        clock = comp.wall_clock()
        repository = comp.resolve_repository(settings, self._repository)
        tool_invoker = comp.resolve_tool_invoker(self._connectors)

        async def _flow() -> RunResult:
            semantics = comp.classify(objective)
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
            router, candidates = comp.resolve_routing(settings, self._router)
            graph = await comp.graph_from_configs(
                plan.agents,
                plan.edges,
                clock=clock,
                gateway=gateway,
                router=router,
                task=semantics,
                candidates=candidates,
                tool_invoker=tool_invoker,
            )
            return await comp.run_graph(
                graph,
                settings=settings,
                clock=clock,
                objective=objective,
                max_supersteps=plan.max_supersteps,
                observer=comp.build_observer(
                    self._middleware, self._handlers, repository=repository
                ),
            )

        return asyncio.run(_flow())

    def pause(self, run_id: str) -> None:
        """Signal ``run_id`` to pause for human review (durable HITL, spec 06 §7).

        A paused run consumes no compute while it awaits ``resume``, ``edit_resume``, or
        ``cancel``, bounded by a 24h deadline after which it times out. Governance also triggers
        this automatically when trust drops below the configured threshold — this method is for an
        operator-initiated pause.

        Raises:
            NotImplementedError: On the local runtime, which is synchronous and has no in-flight
                run to pause. Use ``KORCH_RUNTIME=temporal`` for durable HITL.
            MissingExtraError: If the Temporal runtime is selected without the ``[temporal]`` extra.
        """
        self._signal(run_id, "pause")

    def resume(self, run_id: str) -> None:
        """Lift a pause and let ``run_id`` continue from its checkpointed state.

        Raises:
            NotImplementedError: On the local runtime.
            MissingExtraError: If the Temporal runtime is selected without the ``[temporal]`` extra.
        """
        self._signal(run_id, "resume")

    def cancel(self, run_id: str) -> None:
        """Cancel ``run_id``; it terminates with ``RunStatus.CANCELLED``.

        Raises:
            NotImplementedError: On the local runtime.
            MissingExtraError: If the Temporal runtime is selected without the ``[temporal]`` extra.
        """
        self._signal(run_id, "cancel")

    def edit_resume(
        self,
        run_id: str,
        *,
        updates: Mapping[str, JSONValue] | None = None,
        trust_delta: float = 0.0,
    ) -> None:
        """Apply an operator's context/trust edit to a paused run, then resume it.

        Goes through the same reducer discipline the barrier itself uses (last-value merge for
        ``updates``, a clamped fold for ``trust_delta``) — an edit is as replayable and auditable
        as an agent's own update.

        Args:
            run_id: The paused run to edit and resume.
            updates: Context-channel values to merge into the paused state.
            trust_delta: Folded into ``trust_score``, clamped to ``[0.0, 1.0]``.

        Raises:
            NotImplementedError: On the local runtime.
            MissingExtraError: If the Temporal runtime is selected without the ``[temporal]`` extra.
        """
        self._signal(run_id, "edit_resume", updates=updates, trust_delta=trust_delta)

    def _signal(
        self,
        run_id: str,
        name: str,
        *,
        updates: Mapping[str, JSONValue] | None = None,
        trust_delta: float = 0.0,
    ) -> None:
        """Resolve settings and deliver one durable control signal."""
        settings = self._settings or Settings.from_env()
        asyncio.run(
            comp.send_control_signal(
                settings,
                run_id,
                name,
                runtime=self._runtime,
                updates=updates,
                trust_delta=trust_delta,
            )
        )
