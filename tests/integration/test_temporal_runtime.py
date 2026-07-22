"""Integration tests for the durable Temporal runtime (spec 06 §6.2, P3.3/P3.4).

Requires the ``[temporal]`` extra; skipped otherwise. Runs against Temporal's in-process
time-skipping test server — no external cluster.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import pytest

pytest.importorskip("temporalio")

from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment

from fixtures.graphs import (
    FIXED_TIME,
    initial_state,
    ping_pong_graph,
    worker_lead_graph,
)
from korchestrator.core import AgentGraph
from korchestrator.models.result import RunResult
from korchestrator.runtime.temporal_runtime import (
    PregelMaster,
    PregelRequest,
    TemporalRuntime,
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
    assert result.final_answer == "final answer"
