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

from collections.abc import Mapping
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict
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

__all__ = ["PregelMaster", "PregelRequest", "SuperstepWorker", "TemporalRuntime", "build_worker"]

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


class PregelRequest(BaseModel):
    """The serialisable input to the ``PregelMaster`` workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: AgentState
    node_ids: tuple[str, ...]
    max_supersteps: int = DEFAULT_MAX_SUPERSTEPS
    # Carried across continue-as-new so the reported ``started_at`` spans the whole run.
    started_at: datetime | None = None


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
    """The durable superstep loop. Deterministic workflow scope — time is ``workflow.now()``."""

    @workflow.run
    async def run(self, request: PregelRequest) -> RunResult:
        """Drive supersteps to a terminal :class:`RunResult`, rolling over before the event cap."""
        state = request.state.model_copy(update={"status": RunStatus.RUNNING})
        started_at = request.started_at or workflow.now()
        error_code: str | None = None

        while True:
            if not select_active(request.node_ids, state):
                break
            if state.superstep >= request.max_supersteps:
                error_code = "MAX_SUPERSTEPS_REACHED"
                break
            if workflow.info().get_current_history_length() >= _CONTINUE_AS_NEW_HISTORY_LENGTH:
                workflow.continue_as_new(
                    PregelRequest(
                        state=state,
                        node_ids=request.node_ids,
                        max_supersteps=request.max_supersteps,
                        started_at=started_at,
                    )
                )
            state = await workflow.execute_activity(
                _SUPERSTEP_ACTIVITY,
                args=[state, workflow.now()],
                result_type=AgentState,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_RETRY_POLICY,
            )
            if state.halted:
                break

        return build_result(
            state, started_at=started_at, completed_at=workflow.now(), error_code=error_code
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
    """

    def __init__(
        self,
        graph: AgentGraph,
        *,
        clock: Clock,
        channels: ChannelSchema | None = None,
        client: Client | None = None,
        task_queue: str = _DEFAULT_TASK_QUEUE,
    ) -> None:
        """Store the graph, the clock, the channel schema, and the (optional injected) client."""
        self._graph = graph
        self._clock = clock
        self._channels = channels
        self._client = client
        self._task_queue = task_queue

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
        """Start the ``PregelMaster`` workflow for ``state`` and return its ``run_id``."""
        client = self._require_client()
        await client.start_workflow(
            PregelMaster.run,
            PregelRequest(
                state=state, node_ids=self._graph.node_ids, max_supersteps=max_supersteps
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
        """Deliver a control signal to the workflow.

        Raises:
            NotImplementedError: Durable HITL signals land in P3.5.
        """
        raise NotImplementedError("Durable HITL signals for the Temporal runtime land in P3.5.")
