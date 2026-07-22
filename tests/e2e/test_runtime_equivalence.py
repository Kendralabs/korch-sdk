"""Cross-runtime equivalence, replay, crash recovery, and roll-over (spec 06 §8, spec 09 §5.3).

Requires the ``[temporal]`` extra; runs against Temporal's in-process time-skipping test server.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

pytest.importorskip("temporalio")

from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer

from fixtures.graphs import FIXED_TIME, initial_state, ping_pong_graph, worker_lead_graph
from korchestrator.models.result import RunResult
from korchestrator.runtime import LocalRuntime
from korchestrator.runtime.temporal_runtime import (
    PregelMaster,
    PregelRequest,
    TemporalRuntime,
    build_worker,
)

pytestmark = pytest.mark.temporal

_QUEUE = "korch-equiv"


def _clock() -> object:
    return FIXED_TIME


@pytest.fixture
async def temporal_env() -> AsyncIterator[WorkflowEnvironment]:
    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as env:
        yield env


async def test_local_and_temporal_produce_an_equivalent_result(
    temporal_env: WorkflowEnvironment,
) -> None:
    local = LocalRuntime(worker_lead_graph(), clock=_clock)  # type: ignore[arg-type]
    local_result = await local.wait(await local.start(initial_state("equiv")))

    async with build_worker(temporal_env.client, worker_lead_graph(), task_queue=_QUEUE):
        temporal = TemporalRuntime(
            worker_lead_graph(), clock=_clock, client=temporal_env.client, task_queue=_QUEUE
        )
        temporal_result = await temporal.wait(await temporal.start(initial_state("equiv")))

    # Equivalent excluding runtime-specific timestamps (spec 06 §8): status, final_answer,
    # supersteps, trust_score, error_code, and the message log (deterministic ids + valid_time).
    assert local_result.status == temporal_result.status
    assert local_result.final_answer == temporal_result.final_answer
    assert local_result.supersteps == temporal_result.supersteps
    assert local_result.trust_score == temporal_result.trust_score
    assert local_result.error_code == temporal_result.error_code
    assert local_result.messages == temporal_result.messages


async def test_temporal_history_replays_deterministically(
    temporal_env: WorkflowEnvironment,
) -> None:
    async with build_worker(temporal_env.client, worker_lead_graph(), task_queue=_QUEUE):
        runtime = TemporalRuntime(
            worker_lead_graph(), clock=_clock, client=temporal_env.client, task_queue=_QUEUE
        )
        run_id = await runtime.start(initial_state("replay"))
        await runtime.wait(run_id)
        history = await temporal_env.client.get_workflow_handle(run_id).fetch_history()

    # Replaying the recorded history through the workflow raises on any nondeterminism.
    replayer = Replayer(workflows=[PregelMaster], data_converter=pydantic_data_converter)
    await replayer.replay_workflow(history)


async def test_temporal_run_survives_a_worker_restart(
    temporal_env: WorkflowEnvironment,
) -> None:
    # Start the run paused, then let the worker "crash" (its context exits) while it is parked.
    async with build_worker(temporal_env.client, worker_lead_graph(), task_queue=_QUEUE):
        handle = await temporal_env.client.start_workflow(
            PregelMaster.run,
            PregelRequest(state=initial_state("crash"), node_ids=worker_lead_graph().node_ids),
            id="crash",
            task_queue=_QUEUE,
            start_signal="pause",
        )

    # A fresh worker picks the durable run up from the server and completes it on resume.
    async with build_worker(temporal_env.client, worker_lead_graph(), task_queue=_QUEUE):
        await handle.signal(PregelMaster.resume)
        result: RunResult = await handle.result()

    assert result.status.value == "completed"
    assert result.final_answer == "final answer"


async def test_temporal_rolls_over_before_the_event_cap(
    temporal_env: WorkflowEnvironment,
) -> None:
    # A low continue-as-new threshold forces several roll-overs; the RunResult is unaffected.
    async with build_worker(temporal_env.client, ping_pong_graph(), task_queue=_QUEUE):
        handle = await temporal_env.client.start_workflow(
            PregelMaster.run,
            PregelRequest(
                state=initial_state("rollover"),
                node_ids=ping_pong_graph().node_ids,
                max_supersteps=15,
                continue_as_new_after=25,
            ),
            id="rollover",
            task_queue=_QUEUE,
        )
        result: RunResult = await handle.result()

    assert result.status.value == "completed"
    assert result.supersteps == 15
    assert result.error_code == "MAX_SUPERSTEPS_REACHED"
