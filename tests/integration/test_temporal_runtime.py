"""Integration tests for the durable Temporal runtime (spec 06 §6.2, P3.3/P3.4).

Requires the ``[temporal]`` extra; skipped otherwise. Runs against Temporal's in-process
time-skipping test server — no external cluster.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

import pytest

pytest.importorskip("temporalio")

from temporalio.client import WorkflowHandle
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment

from fixtures.graphs import (
    FIXED_TIME,
    initial_state,
    ping_pong_graph,
    worker_lead_graph,
)
from korchestrator.core import AgentGraph, Edge, Node
from korchestrator.exceptions import ConfigurationError
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState, Message, StateUpdate
from korchestrator.runtime.temporal_runtime import (
    EditResumePayload,
    PregelMaster,
    PregelRequest,
    TemporalRuntime,
    _effective_threshold,
    _should_intervene,
    build_worker,
)

pytestmark = pytest.mark.temporal


@pytest.fixture
async def temporal_env() -> AsyncIterator[WorkflowEnvironment]:
    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as env:
        yield env


async def run_on_temporal(
    env: WorkflowEnvironment,
    graph: AgentGraph,
    *,
    run_id: str = "run",
    max_supersteps: int = 10,
) -> RunResult:
    """Start a worker, run the graph via TemporalRuntime, and return the RunResult."""

    def _clock() -> datetime:
        return FIXED_TIME

    async with build_worker(env.client, graph, task_queue="korch-test"):
        runtime = TemporalRuntime(graph, clock=_clock, client=env.client, task_queue="korch-test")
        started = await runtime.start(initial_state(run_id), max_supersteps=max_supersteps)
        return await runtime.wait(started)


async def test_temporal_runs_a_swarm_to_completion(temporal_env: WorkflowEnvironment) -> None:
    result = await run_on_temporal(temporal_env, worker_lead_graph())
    assert result.status.value == "completed"
    assert result.supersteps == 2
    assert result.final_answer == "final answer"
    assert result.error_code is None


async def test_temporal_enforces_max_supersteps(temporal_env: WorkflowEnvironment) -> None:
    result = await run_on_temporal(temporal_env, ping_pong_graph(), max_supersteps=3)
    assert result.status.value == "completed"
    assert result.supersteps == 3
    assert result.error_code == "MAX_SUPERSTEPS_REACHED"


# --- HITL control signals (P3.5) ----------------------------------------------------------------


async def _start_with_signal(
    env: WorkflowEnvironment,
    graph: AgentGraph,
    *,
    run_id: str,
    start_signal: str,
    max_supersteps: int = 100,
) -> object:
    """Start PregelMaster with a control signal delivered atomically, and return the handle."""
    return await env.client.start_workflow(
        PregelMaster.run,
        PregelRequest(
            state=initial_state(run_id),
            node_ids=graph.node_ids,
            max_supersteps=max_supersteps,
        ),
        id=run_id,
        task_queue="korch-test",
        start_signal=start_signal,
    )


async def test_temporal_cancel_ends_the_run(temporal_env: WorkflowEnvironment) -> None:
    async with build_worker(temporal_env.client, ping_pong_graph(), task_queue="korch-test"):
        handle = await _start_with_signal(
            temporal_env, ping_pong_graph(), run_id="cancel-run", start_signal="cancel"
        )
        result: RunResult = await handle.result()
    assert result.status.value == "cancelled"
    assert result.supersteps < 100


async def test_temporal_pause_without_resume_times_out(
    temporal_env: WorkflowEnvironment,
) -> None:
    # The paused run awaits a signal until the 24h HITL deadline, which time-skipping fast-forwards.
    async with build_worker(temporal_env.client, ping_pong_graph(), task_queue="korch-test"):
        handle = await _start_with_signal(
            temporal_env, ping_pong_graph(), run_id="pause-run", start_signal="pause"
        )
        result: RunResult = await handle.result()
    assert result.status.value == "timed_out"


async def test_temporal_pause_then_resume_completes(
    temporal_env: WorkflowEnvironment,
) -> None:
    async with build_worker(temporal_env.client, worker_lead_graph(), task_queue="korch-test"):
        handle = await _start_with_signal(
            temporal_env, worker_lead_graph(), run_id="resume-run", start_signal="pause"
        )
        await handle.signal(PregelMaster.resume)
        result: RunResult = await handle.result()
    assert result.status.value == "completed"


# --- governance auto-pause (P7.4, spec 06 §7) ---------------------------------------------------


def test_effective_threshold_falls_back_to_the_global_default() -> None:
    assert _effective_threshold("a", {}, 0.5) == 0.5
    assert _effective_threshold("a", {"a": 0.8}, 0.5) == 0.8


def test_should_intervene_checks_every_active_node() -> None:
    state = AgentState(
        run_id="r", objective="summarize the report", trust_score=0.4, transaction_time=FIXED_TIME
    )
    # Neither node has its own threshold; both fall back to the lenient global default.
    assert not _should_intervene(state, ["a", "b"], {}, 0.3)
    # "b" alone breaches its own stricter threshold.
    assert _should_intervene(state, ["a", "b"], {"b": 0.5}, 0.3)
    # A node not in `active` this round cannot trigger an intervention.
    assert not _should_intervene(state, ["a"], {"b": 0.9}, 0.3)


async def _low_trust_ping(state: AgentState) -> StateUpdate:
    message = Message(
        id="x", sender="x", content="ping", recipient="lead", superstep=0, valid_time=FIXED_TIME
    )
    return StateUpdate(
        agent_id="worker", messages=(message,), trust_delta=-0.6, valid_time=FIXED_TIME
    )


async def _lead_answers_once(state: AgentState) -> StateUpdate:
    if state.inbox.get("lead"):
        answer = Message(
            id="x",
            sender="x",
            content="final answer",
            kind="answer",
            superstep=0,
            valid_time=FIXED_TIME,
        )
        return StateUpdate(agent_id="lead", messages=(answer,), halt=True, valid_time=FIXED_TIME)
    return StateUpdate(agent_id="lead", valid_time=FIXED_TIME)


def _low_trust_graph(*, lead_hitl_threshold: float | None = None) -> AgentGraph:
    """A worker whose one message costs 0.6 trust; the lead answers and halts (spec 06 §7 fixture).

    With the default 0.5 global threshold, the drop to 0.4 breaches it for both nodes active that
    round. An explicit ``lead_hitl_threshold`` lets a test give the lead its own, more lenient bar
    so a later superstep (where only the lead is active) does not immediately re-intervene.
    """
    lead_config = AgentConfig(
        id="lead", persona=AgentPersona(role="r"), hitl_threshold=lead_hitl_threshold
    )
    worker_config = AgentConfig(id="worker", persona=AgentPersona(role="r"))
    return AgentGraph(
        [Node(lead_config, _lead_answers_once), Node(worker_config, _low_trust_ping)],
        [Edge("worker", "lead")],
    )


async def test_low_trust_auto_pauses_and_times_out(temporal_env: WorkflowEnvironment) -> None:
    # Uses the raw start_workflow handle (like _start_with_signal above), not
    # TemporalRuntime.start()/wait()'s freshly re-fetched handle: the WorkflowEnvironment's
    # time-skipping test server has a known quirk where a handle re-fetched by run id after a
    # real 24h-timeout skip can't retrieve the completion event, even though the workflow itself
    # completed correctly (verified separately against a real client/handle). Short-lived waits
    # (no real time skip) are unaffected — see test_low_trust_auto_pauses_then_resume_completes.
    graph = _low_trust_graph()
    async with build_worker(temporal_env.client, graph, task_queue="korch-test"):
        handle = await temporal_env.client.start_workflow(
            PregelMaster.run,
            PregelRequest(state=initial_state("low-trust-timeout"), node_ids=graph.node_ids),
            id="low-trust-timeout",
            task_queue="korch-test",
        )
        result: RunResult = await handle.result()
    assert result.status.value == "timed_out"
    assert result.trust_score == pytest.approx(0.4)


async def test_low_trust_auto_pauses_then_resume_completes(
    temporal_env: WorkflowEnvironment,
) -> None:
    # The lead's own lenient threshold keeps superstep 1 (lead-only) from re-triggering a pause.
    graph = _low_trust_graph(lead_hitl_threshold=0.2)
    async with build_worker(temporal_env.client, graph, task_queue="korch-test"):
        runtime = TemporalRuntime(
            graph, clock=lambda: FIXED_TIME, client=temporal_env.client, task_queue="korch-test"
        )
        run_id = await runtime.start(initial_state("low-trust-resume"), max_supersteps=10)
        handle = temporal_env.client.get_workflow_handle_for(PregelMaster.run, run_id)
        await _wait_for_status(handle, "governance_paused")
        await handle.signal(PregelMaster.resume)
        result = await runtime.wait(run_id)
    assert result.status.value == "completed"
    assert result.final_answer == "final answer"
    assert result.trust_score == pytest.approx(0.4)


async def test_low_trust_auto_pauses_then_edit_resume_completes(
    temporal_env: WorkflowEnvironment,
) -> None:
    graph = _low_trust_graph(lead_hitl_threshold=0.2)
    async with build_worker(temporal_env.client, graph, task_queue="korch-test"):
        runtime = TemporalRuntime(
            graph, clock=lambda: FIXED_TIME, client=temporal_env.client, task_queue="korch-test"
        )
        run_id = await runtime.start(initial_state("low-trust-edit"), max_supersteps=10)
        handle = temporal_env.client.get_workflow_handle_for(PregelMaster.run, run_id)
        await _wait_for_status(handle, "governance_paused")
        edit = EditResumePayload(updates={"reviewed_by": "operator-1"}, trust_delta=0.5)
        await runtime.signal(run_id, "edit_resume", {"state_update": edit.model_dump_json()})
        result = await runtime.wait(run_id)
    assert result.status.value == "completed"
    assert result.final_answer == "final answer"
    assert result.trust_score == pytest.approx(0.9)
    assert result.state.context["reviewed_by"] == "operator-1"


async def _wait_for_status(
    handle: WorkflowHandle[PregelMaster, RunResult], status: str, *, attempts: int = 50
) -> None:
    """Poll the workflow's ``status`` query until it reports ``status`` (avoids racing signals)."""
    current = "unknown"
    for _ in range(attempts):
        current = await handle.query(PregelMaster.status)
        if current == status:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"workflow never reached status {status!r} (last saw {current!r})")


# --- signal-only construction (P7.4) -------------------------------------------------------------


async def test_signal_only_runtime_delivers_a_control_signal_without_a_graph(
    temporal_env: WorkflowEnvironment,
) -> None:
    graph = ping_pong_graph()
    async with build_worker(temporal_env.client, graph, task_queue="korch-test"):
        started = TemporalRuntime(
            graph, clock=lambda: FIXED_TIME, client=temporal_env.client, task_queue="korch-test"
        )
        run_id = await started.start(initial_state("signal-only"), max_supersteps=3)

        control = TemporalRuntime(None, clock=lambda: FIXED_TIME, client=temporal_env.client)
        await control.signal(run_id, "cancel", {})
        result = await started.wait(run_id)
    assert result.status.value == "cancelled"


async def test_a_graph_less_runtime_cannot_start_a_run() -> None:
    control = TemporalRuntime(None, clock=lambda: FIXED_TIME)
    with pytest.raises(ConfigurationError):
        await control.start(initial_state("no-graph"))
