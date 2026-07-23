"""Adapter layer — the durable Temporal runtime ([temporal] extra).

``temporalio`` is imported at module top **here only**, which is legal because this module is loaded
lazily (via ``runtime.resolve_runtime`` / ``_resolve_temporal``); ``import korchestrator.runtime``
never imports it, so the base install stays ``pydantic``-only. The Temporal workflow decorators
require the import at definition time, so the confinement is at the module-load boundary, not the
import statement (CLAUDE.md §3 intent: the base install must not touch temporalio).

Design (spec 06 §6.2): a single ``PregelMaster`` workflow drives the superstep loop in deterministic
workflow scope (``workflow.now()``, no randomness), invoking **one ``SuperstepActivity`` per
superstep** for the nondeterministic agent compute. The workflow holds only serialisable data (the
``AgentState`` and the node ids); the graph's live callables live in the activity's worker. Domain
models cross the boundary via the pydantic data converter.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field
from temporalio import activity, workflow
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

with workflow.unsafe.imports_passed_through():
    from korchestrator.core.channels import ChannelSchema
    from korchestrator.core.graph import AgentGraph
    from korchestrator.core.pregel import (
        DEFAULT_MAX_SUPERSTEPS,
        Clock,
        PregelRunner,
        build_result,
        select_active,
    )
    from korchestrator.exceptions import ConfigurationError
    from korchestrator.models.result import RunResult
    from korchestrator.models.state import AgentState, RunStatus
    from korchestrator.types import JSONValue

__all__ = [
    "EditResumePayload",
    "PregelMaster",
    "PregelRequest",
    "SuperstepWorker",
    "TemporalRuntime",
    "build_worker",
]

_SUPERSTEP_ACTIVITY = "korch_superstep"
_DEFAULT_TASK_QUEUE = "korchestrator"

# The activity's per-attempt deadline and its bounded, jittered retry policy (spec 06 §7). Temporal
# applies jitter automatically. The non-retryable errors are the definitionally-terminal ones — a
# bad request must not be retried three times.
_ACTIVITY_TIMEOUT = timedelta(seconds=300)
_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=[
        "ValidationError",
        "AuthError",
        "QuotaExceededError",
        "GovernanceHaltError",
    ],
)

# Roll over to a fresh workflow run before Temporal's 50k-event cap (spec 06 §7). Well below the
# cap; a test lowers it to exercise the roll-over path.
_CONTINUE_AS_NEW_HISTORY_LENGTH = 10_000

# A paused run consumes no compute while it awaits a control signal, bounded by this deadline
# (spec 06 §7); on expiry it transitions to TIMED_OUT. Configurable via TEMPORAL_HITL_TIMEOUT in P8.
_HITL_TIMEOUT = timedelta(hours=24)


class PregelRequest(BaseModel):
    """The serialisable input to the ``PregelMaster`` workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: AgentState
    node_ids: tuple[str, ...]
    max_supersteps: int = DEFAULT_MAX_SUPERSTEPS
    # Roll over to a fresh workflow run once history reaches this many events. A test lowers it to
    # exercise the roll-over path deterministically without touching the sandboxed module constant.
    continue_as_new_after: int = _CONTINUE_AS_NEW_HISTORY_LENGTH
    # Carried across continue-as-new so the reported ``started_at`` spans the whole run.
    started_at: datetime | None = None
    # HITL governance (P7.4, spec 06 §7): each node's own hitl_threshold (built from the graph's
    # AgentConfigs at TemporalRuntime.start(), since the graph itself — with its live callables —
    # never crosses the workflow boundary); global_threshold is the GOVERNANCE_TRUST_THRESHOLD
    # fallback for a node with none of its own.
    hitl_thresholds: Mapping[str, float] = Field(default_factory=dict)
    global_threshold: float = 0.5


class EditResumePayload(BaseModel):
    """The ``edit_resume`` signal's body: an operator's context/trust edit (spec 06 §7).

    Deliberately narrower than a full :class:`~korchestrator.models.state.StateUpdate` — it carries
    context-channel updates and a trust delta, not messages. Message routing needs the graph's
    edges, which never cross the workflow boundary (the graph carries live, non-serialisable
    callables); an operator editing context/trust needs neither.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    updates: Mapping[str, JSONValue] = Field(default_factory=dict)
    trust_delta: float = Field(default=0.0, ge=-1.0, le=1.0)


def _effective_threshold(
    node_id: str, hitl_thresholds: Mapping[str, float], global_threshold: float
) -> float:
    """Return ``node_id``'s own HITL threshold, else the ``global_threshold`` fallback."""
    return hitl_thresholds.get(node_id, global_threshold)


def _should_intervene(
    state: AgentState,
    active: Sequence[str],
    hitl_thresholds: Mapping[str, float],
    global_threshold: float,
) -> bool:
    """Return whether ``state.trust_score`` breaches any active node's effective threshold.

    Checked once per superstep, against the nodes that were active *this* round — the ones whose
    ``trust_delta`` just contributed to the score (spec 06 §7: "an agent's trust score is below
    hitl_threshold"). ``trust_score`` is one run-wide value, not per-agent, so the most
    conservative reading applies: any active agent's own bar being missed pauses the whole run.
    """
    return any(
        state.trust_score < _effective_threshold(node_id, hitl_thresholds, global_threshold)
        for node_id in active
    )


class SuperstepWorker:
    """Holds the live graph and exposes the compute activity for one superstep."""

    def __init__(self, graph: AgentGraph, channels: ChannelSchema | None = None) -> None:
        """Store the graph (with its agent callables) and the channel schema."""
        self._graph = graph
        self._channels = channels

    @activity.defn(name=_SUPERSTEP_ACTIVITY)
    async def run_superstep(self, state: AgentState, tx_time: datetime) -> AgentState:
        """Compute one superstep's active agents and return the reduced next state.

        Nondeterministic agent work happens here (the activity boundary); ``tx_time`` is supplied by
        the workflow's replay-safe clock so the barrier's ``transaction_time`` stays deterministic.
        """
        runner = PregelRunner(self._graph, clock=lambda: tx_time, channels=self._channels)
        return await runner.run_superstep(state)


@workflow.defn(name="korch_pregel_master")
class PregelMaster:
    """The durable superstep loop. Deterministic workflow scope — time is ``workflow.now()``.

    Accepts durable HITL control signals: ``cancel`` ends the run as ``cancelled``; ``pause`` parks
    it (status ``governance_paused``, consuming no compute) until ``resume``, ``edit_resume``, or
    ``cancel``, bounded by a 24h deadline after which it is ``timed_out`` (spec 06 §7).
    ``edit_resume`` applies an operator's context/trust edit through the same clamped-fold
    arithmetic the barrier uses, then resumes. The loop also **pauses itself**: after each
    superstep, if the resulting ``trust_score`` breaches any active node's effective HITL
    threshold, it parks exactly as an externally signalled ``pause`` would — governance
    intervention and an operator's own ``pause`` share one mechanism.
    """

    def __init__(self) -> None:
        """Initialise the mutable control-signal flags and any pending operator edit."""
        self._cancelled = False
        self._paused = False
        self._pending_edit: EditResumePayload | None = None
        self._state: AgentState | None = None

    @workflow.query
    def status(self) -> str:
        """Return the run's current :class:`~korchestrator.models.state.RunStatus` value.

        A non-blocking query — the idiomatic way to check whether a run has reached
        ``governance_paused`` without waiting for it to finish (:meth:`TemporalRuntime.wait`
        blocks until the workflow's terminal return, not a mid-run pause).
        """
        return self._state.status.value if self._state is not None else RunStatus.STARTED.value

    @workflow.signal
    def cancel(self) -> None:
        """Request cancellation; the loop ends the run as ``cancelled``."""
        self._cancelled = True

    @workflow.signal
    def pause(self) -> None:
        """Request a pause; the loop parks the run until ``resume``, ``edit_resume``, or ``cancel``.

        This is the same flag governance's own auto-pause sets — an operator-initiated pause and
        a trust-threshold intervention are indistinguishable once parked.
        """
        self._paused = True

    @workflow.signal
    def resume(self) -> None:
        """Lift a pause; the loop continues from the checkpointed state."""
        self._paused = False

    @workflow.signal
    def edit_resume(self, payload: str) -> None:
        """Queue an operator's context/trust edit and lift the pause (spec 06 §7).

        ``payload`` is an :class:`EditResumePayload`, JSON-encoded — Temporal signal arguments
        are plain data, and this keeps the wire shape identical to
        :meth:`~korchestrator.interfaces.IDurableRuntime.signal`'s ``Mapping[str, str]`` contract.
        """
        self._pending_edit = EditResumePayload.model_validate_json(payload)
        self._paused = False

    @workflow.run
    async def run(self, request: PregelRequest) -> RunResult:
        """Drive supersteps to a terminal :class:`RunResult`, honouring control signals."""
        state = request.state.model_copy(update={"status": RunStatus.RUNNING})
        started_at = request.started_at or workflow.now()
        error_code: str | None = None

        while True:
            self._state = state
            if self._cancelled:
                return self._terminal(state, started_at, RunStatus.CANCELLED)
            if self._paused:
                state = state.model_copy(update={"status": RunStatus.GOVERNANCE_PAUSED})
                self._state = state
                try:
                    await workflow.wait_condition(
                        lambda: not self._paused or self._cancelled, timeout=_HITL_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    return self._terminal(state, started_at, RunStatus.TIMED_OUT)
                if self._pending_edit is not None:
                    state = self._apply_edit(state, self._pending_edit)
                    self._pending_edit = None
                # Woke on resume, edit_resume, or cancel; loop back — the top handles a pending
                # cancel.
                state = state.model_copy(update={"status": RunStatus.RUNNING})
                continue
            active = select_active(request.node_ids, state)
            if not active:
                break
            if state.superstep >= request.max_supersteps:
                error_code = "MAX_SUPERSTEPS_REACHED"
                break
            if workflow.info().get_current_history_length() >= request.continue_as_new_after:
                workflow.continue_as_new(
                    PregelRequest(
                        state=state,
                        node_ids=request.node_ids,
                        max_supersteps=request.max_supersteps,
                        continue_as_new_after=request.continue_as_new_after,
                        started_at=started_at,
                        hitl_thresholds=request.hitl_thresholds,
                        global_threshold=request.global_threshold,
                    )
                )
            state = await workflow.execute_activity(
                _SUPERSTEP_ACTIVITY,
                args=[state, workflow.now()],
                result_type=AgentState,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_RETRY_POLICY,
            )
            if _should_intervene(state, active, request.hitl_thresholds, request.global_threshold):
                self._paused = True
                continue
            if state.halted:
                break

        return build_result(
            state, started_at=started_at, completed_at=workflow.now(), error_code=error_code
        )

    @staticmethod
    def _apply_edit(state: AgentState, edit: EditResumePayload) -> AgentState:
        """Fold an operator's context/trust edit into ``state``.

        Spec 06 §7's "through the reducers" intent, scoped to what :class:`EditResumePayload`
        carries: context updates merge last-value, and ``trust_delta`` folds via the same clamp
        the barrier itself uses.
        """
        new_context = {**state.context, **edit.updates}
        new_trust = max(0.0, min(1.0, state.trust_score + edit.trust_delta))
        return state.model_copy(
            update={
                "context": new_context,
                "trust_score": new_trust,
                "transaction_time": workflow.now(),
            }
        )

    def _terminal(self, state: AgentState, started_at: datetime, status: RunStatus) -> RunResult:
        """Build a signal-terminated result (``cancelled`` / ``timed_out``)."""
        return build_result(
            state, started_at=started_at, completed_at=workflow.now(), status=status
        )


def build_worker(
    client: Client,
    graph: AgentGraph,
    *,
    channels: ChannelSchema | None = None,
    task_queue: str = _DEFAULT_TASK_QUEUE,
) -> Worker:
    """Build a Temporal worker that serves ``PregelMaster`` and the graph-bound superstep activity.

    The caller runs this worker (``async with build_worker(...)``); it is the process that executes
    the durable workflow. The client MUST use ``temporalio.contrib.pydantic``'s data converter
    so the domain models cross the boundary.
    """
    superstep = SuperstepWorker(graph, channels)
    return Worker(
        client,
        task_queue=task_queue,
        workflows=[PregelMaster],
        activities=[superstep.run_superstep],
    )


class TemporalRuntime:
    """Durable ``IDurableRuntime`` backed by a Temporal ``PregelMaster`` workflow.

    Client-side driver: ``start`` launches the workflow, ``wait`` awaits its result, ``signal``
    delivers a control signal. A worker built with :func:`build_worker` must be running to execute
    the workflow. The client is injected (tests supply one from a ``WorkflowEnvironment``); a
    connection helper for production wiring lands with the façade in P4.

    ``graph`` is optional: delivering a control signal to an already-running workflow needs only a
    client and a ``run_id``, not the graph (its live callables never cross the workflow boundary
    anyway). Construct with ``graph=None`` for a signal-only instance; :meth:`start` requires a
    real graph and raises :class:`~korchestrator.exceptions.ConfigurationError` without one.
    """

    def __init__(
        self,
        graph: AgentGraph | None,
        *,
        clock: Clock,
        channels: ChannelSchema | None = None,
        client: Client | None = None,
        task_queue: str = _DEFAULT_TASK_QUEUE,
        global_threshold: float = 0.5,
    ) -> None:
        """Store the graph, the clock, the channel schema, and the (optional injected) client."""
        self._graph = graph
        self._clock = clock
        self._channels = channels
        self._client = client
        self._task_queue = task_queue
        self._global_threshold = global_threshold

    def _require_client(self) -> Client:
        if self._client is None:
            raise ConfigurationError(
                "TemporalRuntime needs a Temporal client. Inject one (client=...) or wire the "
                "production connection at the composition root.",
                code="KORCH_CONFIG_INVALID",
            )
        return self._client

    def now(self) -> datetime:
        """Return the injected clock's current time."""
        return self._clock()

    async def start(
        self, state: AgentState, *, max_supersteps: int = DEFAULT_MAX_SUPERSTEPS
    ) -> str:
        """Start the ``PregelMaster`` workflow for ``state`` and return its ``run_id``.

        Raises:
            ConfigurationError: If this instance was constructed without a graph (``graph=None``)
                — a signal-only instance for delivering control signals to an existing run.
        """
        if self._graph is None:
            raise ConfigurationError(
                "This TemporalRuntime was constructed without a graph (graph=None), so it can "
                "only deliver control signals to an existing run, not start one. Construct one "
                "with graph=<AgentGraph> to start a run.",
                code="KORCH_CONFIG_INVALID",
            )
        client = self._require_client()
        hitl_thresholds = {
            node.id: node.config.hitl_threshold
            for node in self._graph.nodes
            if node.config.hitl_threshold is not None
        }
        await client.start_workflow(
            PregelMaster.run,
            PregelRequest(
                state=state,
                node_ids=self._graph.node_ids,
                max_supersteps=max_supersteps,
                hitl_thresholds=hitl_thresholds,
                global_threshold=self._global_threshold,
            ),
            id=state.run_id,
            task_queue=self._task_queue,
        )
        return state.run_id

    async def wait(self, run_id: str, *, timeout_seconds: float | None = None) -> RunResult:
        """Block until the workflow ``run_id`` completes and return its :class:`RunResult`."""
        client = self._require_client()
        handle: WorkflowHandle[PregelMaster, RunResult] = client.get_workflow_handle_for(
            PregelMaster.run, run_id
        )
        return await handle.result()

    async def signal(self, run_id: str, name: str, payload: Mapping[str, str]) -> None:
        """Deliver a durable control signal (``cancel``/``pause``/``resume``/``edit_resume``).

        ``edit_resume``'s payload carries the JSON-encoded :class:`EditResumePayload` under the
        ``"state_update"`` key; the composition root (``services.pause``/``resume``/``cancel``/
        ``edit_resume``) is the one place that builds it, so callers never see the wire format.
        """
        client = self._require_client()
        handle = client.get_workflow_handle(run_id)
        if name == "edit_resume":
            await handle.signal(PregelMaster.edit_resume, payload.get("state_update", "{}"))
            return
        await handle.signal(name)
