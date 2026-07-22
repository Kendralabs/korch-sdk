"""Adapter layer. Imports: korchestrator.core, exceptions, models, stdlib. No temporalio.

The in-process ``IDurableRuntime`` (``KORCH_RUNTIME=local``) — the default for dev, CI, and
embedding. It drives the same ``PregelRunner`` loop against an injected clock. Crash recovery is
out of scope for this adapter: the process **is** the durability boundary (spec 06 §6.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from korchestrator.core.channels import ChannelSchema
from korchestrator.core.graph import AgentGraph
from korchestrator.core.pregel import Clock, PregelRunner
from korchestrator.exceptions import ValidationError
from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState

__all__ = ["LocalRuntime"]


class LocalRuntime:
    """In-process runtime that runs a graph to completion with zero infrastructure.

    Collaborators are injected at construction (spec 03 §5, ADR 0010): the ``graph`` to run, the
    replay-safe ``clock``, and the channel schema. ``start`` runs the loop synchronously and stores
    the result; ``wait`` returns it. There is no external durability — a crash loses the run.

    Args:
        graph: The validated agent graph to run.
        clock: A zero-argument callable returning the current time (injected).
        channels: The channel-to-reducer bindings. Defaults to all-``LastValue``.

    Example:
        >>> import asyncio
        >>> from datetime import datetime, timezone
        >>> from korchestrator.core import AgentGraph, Node
        >>> from korchestrator.models.agent import AgentConfig, AgentPersona
        >>> from korchestrator.models.state import AgentState, StateUpdate
        >>> from korchestrator.runtime import LocalRuntime
        >>> fixed = datetime(2026, 7, 22, tzinfo=timezone.utc)
        >>> async def finish(state):
        ...     return StateUpdate(agent_id="lead", valid_time=fixed, halt=True)
        >>> cfg = AgentConfig(id="lead", persona=AgentPersona(role="lead"))
        >>> runtime = LocalRuntime(AgentGraph([Node(cfg, finish)]), clock=lambda: fixed)
        >>> state = AgentState(run_id="r", objective="summarize the report", transaction_time=fixed)
        >>> async def go():
        ...     run_id = await runtime.start(state)
        ...     return await runtime.wait(run_id)
        >>> asyncio.run(go()).status.value
        'completed'
    """

    def __init__(
        self,
        graph: AgentGraph,
        *,
        clock: Clock,
        channels: ChannelSchema | None = None,
    ) -> None:
        """Store the injected graph, clock, and channel schema."""
        self._graph = graph
        self._clock = clock
        self._channels = channels
        self._results: dict[str, RunResult] = {}

    def now(self) -> datetime:
        """Return the injected clock's current time."""
        return self._clock()

    async def start(self, state: AgentState, *, max_supersteps: int = 10) -> str:
        """Run the graph to completion in-process and return the run id.

        The local runtime is synchronous: the run finishes before ``start`` returns, and the result
        is retrievable via :meth:`wait`.
        """
        runner = PregelRunner(
            self._graph,
            clock=self._clock,
            channels=self._channels,
            max_supersteps=max_supersteps,
        )
        self._results[state.run_id] = await runner.run(state)
        return state.run_id

    async def wait(self, run_id: str, *, timeout_seconds: float | None = None) -> RunResult:
        """Return the completed :class:`RunResult` for ``run_id``.

        Raises:
            ValidationError: If ``run_id`` was never started on this runtime.
        """
        try:
            return self._results[run_id]
        except KeyError as exc:
            raise ValidationError(
                f"No run {run_id!r} on this runtime. Call start() before wait().",
                code="KORCH_VALIDATION_FAILED",
            ) from exc

    async def signal(self, run_id: str, name: str, payload: Mapping[str, str]) -> None:
        """Deliver a control signal.

        Raises:
            NotImplementedError: Durable HITL signals for the local runtime land in P3.5.
        """
        raise NotImplementedError("Durable HITL signals for the local runtime land in P3.5.")
