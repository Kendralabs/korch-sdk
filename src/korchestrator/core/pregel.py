"""Kernel layer (L1), framework-free. Imports: core (channels/graph/reducers), models, exceptions.

The Pregel BSP superstep runner: activation, the concurrent compute phase (``asyncio.gather``), the
synchronise barrier, the reduce step, message routing, and halting. Deterministic and framework-free
— the graph's node callables and the clock are injected; the runner constructs nothing and reads no
wall clock (spec 06 §1-§5).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from korchestrator.core.channels import ChannelSchema
from korchestrator.core.graph import AgentGraph
from korchestrator.core.reducers import Delta
from korchestrator.exceptions import ValidationError
from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState, Message, RunStatus, StateUpdate
from korchestrator.types import JSONValue

__all__ = ["Clock", "PregelRunner", "SuperstepObserver", "build_result", "select_active"]

# The injected, replay-safe clock. Under Temporal this is ``workflow.now()``; locally, a monotone
# injected clock. Workflow-path code MUST use this, never ``datetime.now()`` (spec 06 §5).
Clock = Callable[[], datetime]

DEFAULT_MAX_SUPERSTEPS = 10


@runtime_checkable
class SuperstepObserver(Protocol):
    """Observe superstep boundaries without influencing the barrier (spec 07 §9).

    The runtime may inject an observer so middleware and event hooks can fire around each superstep.
    It is called only by the in-process run loop, never in Temporal workflow scope, so it cannot
    affect the replay contract. Implementations MUST NOT raise (they isolate their own errors) and
    MUST NOT mutate ``state`` — the barrier result is already computed when they run.
    """

    async def before_superstep(self, state: AgentState) -> None:
        """Called with the state about to be computed, before the compute phase."""
        ...

    async def after_superstep(self, state: AgentState) -> None:
        """Called with the state produced by the barrier, after reducers and routing."""
        ...


def select_active(node_ids: Sequence[str], state: AgentState) -> tuple[str, ...]:
    """Return the node ids that compute this superstep, in ``node_ids`` order (spec 06 §2).

    Superstep 0 activates every node; later supersteps activate only nodes with a non-empty inbox.
    A node that has halted is never reactivated. Pure over ``(node_ids, state)`` so a runtime can
    compute activation from serialised topology in workflow scope (the Temporal ``PregelMaster``).
    """
    halted = set(state.halted_agents)
    if state.superstep == 0:
        return tuple(node_id for node_id in node_ids if node_id not in halted)
    return tuple(
        node_id for node_id in node_ids if node_id not in halted and state.inbox.get(node_id)
    )


def build_result(
    state: AgentState,
    *,
    started_at: datetime,
    completed_at: datetime,
    error_code: str | None = None,
    status: RunStatus = RunStatus.COMPLETED,
) -> RunResult:
    """Assemble the terminal :class:`RunResult` from the final state (shared by both runtimes).

    ``status`` defaults to ``COMPLETED``; a runtime passes ``CANCELLED`` or ``TIMED_OUT`` when a
    control signal or a HITL deadline ends the run.
    """
    final_answer = "\n".join(
        message.content for message in state.messages if message.kind == "answer"
    )
    return RunResult(
        run_id=state.run_id,
        status=status,
        final_answer=final_answer,
        supersteps=state.superstep,
        messages=state.messages,
        state=state.model_copy(update={"status": status}),
        trust_score=state.trust_score,
        error_code=error_code,
        error=("Run reached the max_supersteps bound before completing." if error_code else None),
        started_at=started_at,
        completed_at=completed_at,
    )


class PregelRunner:
    """Runs a graph as a sequence of deterministic Bulk Synchronous Parallel supersteps.

    Collaborators are injected: the ``graph`` carries each node's compute callable, and ``clock``
    supplies replay-safe time. The runner never constructs an agent or reads the wall clock.

    Args:
        graph: The validated agent graph to run.
        clock: A zero-argument callable returning the current time (injected, replay-safe).
        channels: The channel-to-reducer bindings. Defaults to all-``LastValue``.
        max_supersteps: The hard halt bound. Defaults to 10.

    Example:
        >>> import asyncio
        >>> from datetime import datetime, timezone
        >>> from korchestrator.core import AgentGraph, Node
        >>> from korchestrator.core.pregel import PregelRunner
        >>> from korchestrator.models.agent import AgentConfig, AgentPersona
        >>> from korchestrator.models.state import AgentState, StateUpdate
        >>> fixed = datetime(2026, 7, 21, tzinfo=timezone.utc)
        >>> async def finish(state):
        ...     return StateUpdate(agent_id="lead", valid_time=fixed, halt=True)
        >>> cfg = AgentConfig(id="lead", persona=AgentPersona(role="lead"))
        >>> graph = AgentGraph([Node(cfg, finish)])
        >>> runner = PregelRunner(graph, clock=lambda: fixed)
        >>> start = AgentState(run_id="r", objective="summarize the report", transaction_time=fixed)
        >>> result = asyncio.run(runner.run(start))
        >>> (result.status.value, result.supersteps)
        ('completed', 1)
    """

    def __init__(
        self,
        graph: AgentGraph,
        *,
        clock: Clock,
        channels: ChannelSchema | None = None,
        max_supersteps: int = DEFAULT_MAX_SUPERSTEPS,
        observer: SuperstepObserver | None = None,
    ) -> None:
        """Store the injected graph, clock, channel schema, halt bound, and optional observer."""
        self._graph = graph
        self._clock = clock
        self._channels = channels if channels is not None else ChannelSchema()
        self._max_supersteps = max_supersteps
        self._observer = observer

    # --- activation -----------------------------------------------------------------------------

    def active_node_ids(self, state: AgentState) -> tuple[str, ...]:
        """Return the node ids that compute this superstep, in sorted order (spec 06 §2).

        Superstep 0 activates every node; later supersteps activate only nodes with a non-empty
        inbox. A node that has halted is never reactivated.
        """
        return select_active(self._graph.node_ids, state)

    # --- one superstep --------------------------------------------------------------------------

    async def run_superstep(self, state: AgentState) -> AgentState:
        """Run one superstep and return the next :class:`AgentState`.

        Computes the active nodes concurrently against the frozen ``state`` snapshot, synchronises
        at the barrier, applies the channel reducers, routes messages, and stamps transaction time.
        Returns ``state`` unchanged when no node is active (a terminal superstep).
        """
        active = self.active_node_ids(state)
        if not active:
            return state
        nodes = [self._graph.get_node(node_id) for node_id in active]
        raw_updates = await asyncio.gather(*(node.compute(state) for node in nodes))
        updates = self.synchronize(raw_updates, active)
        return self._apply(state, updates)

    def synchronize(self, updates: list[StateUpdate], active: tuple[str, ...]) -> list[StateUpdate]:
        """Validate the barrier's updates and return them in canonical (``agent_id``) order.

        Raises:
            ValidationError: If an update's ``agent_id`` is not one of the active nodes, or two
                updates claim the same ``agent_id``.
        """
        active_set = set(active)
        by_agent: dict[str, StateUpdate] = {}
        for update in updates:
            if update.agent_id not in active_set:
                raise ValidationError(
                    f"Agent {update.agent_id!r} emitted a StateUpdate but was not active this "
                    "superstep. An update's agent_id must match the emitting node.",
                    code="KORCH_VALIDATION_FAILED",
                )
            if update.agent_id in by_agent:
                raise ValidationError(
                    f"Agent {update.agent_id!r} emitted more than one StateUpdate in a superstep.",
                    code="KORCH_VALIDATION_FAILED",
                )
            by_agent[update.agent_id] = update
        return [by_agent[agent_id] for agent_id in sorted(by_agent)]

    def _apply(self, state: AgentState, updates: list[StateUpdate]) -> AgentState:
        """Reduce channels, route messages, compute halting, and build the next state."""
        transaction_time = self._clock()
        superstep = state.superstep

        new_context = self._reduce_context(state, updates)
        new_inbox, answer_messages = self._route_messages(state, updates, superstep)

        newly_halted = {update.agent_id for update in updates if update.halt}
        halted_agents = tuple(sorted(set(state.halted_agents) | newly_halted))
        all_active_halted = all(update.halt for update in updates)

        return state.model_copy(
            update={
                "context": new_context,
                "inbox": new_inbox,
                "messages": (*state.messages, *answer_messages),
                "superstep": superstep + 1,
                "halted": all_active_halted,
                "halted_agents": halted_agents,
                "status": RunStatus.RUNNING,
                "transaction_time": transaction_time,
            }
        )

    def _reduce_context(
        self, state: AgentState, updates: list[StateUpdate]
    ) -> dict[str, JSONValue]:
        """Merge each written channel's deltas through its bound reducer (deterministic order)."""
        channel_deltas: dict[str, list[Delta]] = {}
        for update in updates:
            for channel, value in update.updates.items():
                channel_deltas.setdefault(channel, []).append((update.agent_id, value))
        new_context = dict(state.context)
        for channel, deltas in channel_deltas.items():
            reducer = self._channels.reducer_for(channel)
            new_context[channel] = reducer(new_context.get(channel), deltas)
        return new_context

    def _route_messages(
        self, state: AgentState, updates: list[StateUpdate], superstep: int
    ) -> tuple[dict[str, tuple[Message, ...]], list[Message]]:
        """Assign deterministic ids and route each message to its target inboxes.

        Inboxes are rebuilt fresh each superstep (delivered exactly once, to the next superstep).
        ``answer`` messages additionally accumulate into the run's answer log.
        """
        inbox: dict[str, list[Message]] = {}
        answers: list[Message] = []
        for update in updates:  # already in agent_id order
            for index, message in enumerate(update.messages):
                stamped = message.model_copy(
                    update={
                        "id": f"{state.run_id}:{superstep}:{update.agent_id}:{index}",
                        "sender": update.agent_id,
                        "superstep": superstep,
                    }
                )
                for target in self._targets(update.agent_id, stamped):
                    inbox.setdefault(target, []).append(stamped)
                if stamped.kind == "answer":
                    answers.append(stamped)
        return {target: tuple(messages) for target, messages in inbox.items()}, answers

    def _targets(self, sender: str, message: Message) -> tuple[str, ...]:
        """Resolve a message's delivery targets (spec 06 §4).

        A ``recipient=None`` message broadcasts along every outbound edge; an explicit recipient is
        delivered only if ``(sender, recipient)`` is an edge.

        Raises:
            ValidationError: If an explicit recipient is not connected to the sender by an edge.
        """
        if message.recipient is None:
            return self._graph.outbound(sender)
        if not self._graph.has_edge(sender, message.recipient):
            raise ValidationError(
                f"Message from {sender!r} to {message.recipient!r} cannot be delivered: no "
                f"edge {sender!r} -> {message.recipient!r} in the graph.",
                code="KORCH_VALIDATION_FAILED",
            )
        return (message.recipient,)

    # --- the run loop ---------------------------------------------------------------------------

    async def run(self, state: AgentState) -> RunResult:
        """Drive supersteps to a terminal :class:`RunResult`.

        Halts when no node is active, when every active node halted, or when the ``max_supersteps``
        bound is reached (spec 06 §2). The kernel always terminates in ``completed``; the paused,
        failed, and timed-out statuses belong to the runtime and governance layers.
        """
        started_at = self._clock()
        current = state.model_copy(update={"status": RunStatus.RUNNING})
        error_code: str | None = None

        while True:
            if not self.active_node_ids(current):
                break
            if current.superstep >= self._max_supersteps:
                error_code = "MAX_SUPERSTEPS_REACHED"
                break
            if self._observer is not None:
                await self._observer.before_superstep(current)
            current = await self.run_superstep(current)
            if self._observer is not None:
                await self._observer.after_superstep(current)
            if current.halted:
                break

        return build_result(
            current, started_at=started_at, completed_at=self._clock(), error_code=error_code
        )
