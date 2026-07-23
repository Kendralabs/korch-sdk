"""Unit tests for the in-process local runtime and runtime selection (spec 06 §6, P3.1/P3.2)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from korchestrator.config import Settings
from korchestrator.core import AgentGraph, Edge, Node, PregelRunner
from korchestrator.exceptions import MissingExtraError, ValidationError
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, Message, StateUpdate
from korchestrator.runtime import LocalRuntime, resolve_runtime

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _node(agent_id: str, compute: object) -> Node:
    return Node(AgentConfig(id=agent_id, persona=AgentPersona(role="r")), compute)  # type: ignore[arg-type]


async def _worker(state: AgentState) -> StateUpdate:
    if state.superstep == 0:
        msg = Message(
            id="x", sender="x", content="data", recipient="lead", superstep=0, valid_time=NOW
        )
        return StateUpdate(agent_id="worker", messages=(msg,), valid_time=NOW)
    return StateUpdate(agent_id="worker", valid_time=NOW)


async def _lead(state: AgentState) -> StateUpdate:
    if state.inbox.get("lead"):
        answer = Message(
            id="x", sender="x", content="final answer", kind="answer", superstep=0, valid_time=NOW
        )
        return StateUpdate(agent_id="lead", messages=(answer,), halt=True, valid_time=NOW)
    return StateUpdate(agent_id="lead", valid_time=NOW)


def _graph() -> AgentGraph:
    return AgentGraph([_node("lead", _lead), _node("worker", _worker)], [Edge("worker", "lead")])


def _start() -> AgentState:
    return AgentState(run_id="run", objective="summarize the report", transaction_time=NOW)


async def test_local_runtime_runs_to_completion(make_clock: Callable[..., object]) -> None:
    runtime = LocalRuntime(_graph(), clock=make_clock())  # type: ignore[arg-type]
    run_id = await runtime.start(_start())
    result = await runtime.wait(run_id)
    assert run_id == "run"
    assert result.status.value == "completed"
    assert result.final_answer == "final answer"
    assert result.supersteps == 2


def test_now_returns_the_injected_clock(make_clock: Callable[..., object]) -> None:
    runtime = LocalRuntime(_graph(), clock=make_clock())  # type: ignore[arg-type]
    assert runtime.now() == NOW


async def test_wait_for_an_unknown_run_raises(make_clock: Callable[..., object]) -> None:
    runtime = LocalRuntime(_graph(), clock=make_clock())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        await runtime.wait("never-started")


async def test_signal_is_not_implemented_until_p3_5(make_clock: Callable[..., object]) -> None:
    runtime = LocalRuntime(_graph(), clock=make_clock())  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await runtime.signal("run", "resume", {})


def test_resolve_runtime_selects_local(make_clock: Callable[..., object]) -> None:
    runtime = resolve_runtime(Settings(korch_runtime="local"), _graph(), clock=make_clock())  # type: ignore[arg-type]
    assert isinstance(runtime, LocalRuntime)


def test_resolve_runtime_temporal_resolves_to_the_durable_adapter(
    make_clock: Callable[..., object],
) -> None:
    pytest.importorskip("temporalio")
    runtime = resolve_runtime(Settings(korch_runtime="temporal"), _graph(), clock=make_clock())  # type: ignore[arg-type]
    assert type(runtime).__name__ == "TemporalRuntime"


def test_resolve_runtime_temporal_without_the_extra_raises_missing_extra(
    make_clock: Callable[..., object],
) -> None:
    # Deterministic regardless of whether temporalio actually happens to be installed in this
    # environment — simulates the extra being absent rather than depending on it. Also blanks
    # korchestrator.runtime.temporal_runtime: once it's cached (e.g. an earlier test already
    # imported it), `from ...temporal_runtime import TemporalRuntime` would resolve from the
    # cache without re-running its top-level `import temporalio`, masking the blank-out.
    import sys
    from unittest import mock

    with (
        mock.patch.dict(
            sys.modules, {"temporalio": None, "korchestrator.runtime.temporal_runtime": None}
        ),
        pytest.raises(MissingExtraError) as info,
    ):
        resolve_runtime(Settings(korch_runtime="temporal"), _graph(), clock=make_clock())  # type: ignore[arg-type]
    assert info.value.code == "KORCH_MISSING_EXTRA"


async def test_local_runtime_matches_a_direct_runner(make_clock: Callable[..., object]) -> None:
    # The runtime is a thin driver over PregelRunner; with equal clocks the results are identical.
    runtime = LocalRuntime(_graph(), clock=make_clock())  # type: ignore[arg-type]
    run_id = await runtime.start(_start())
    via_runtime = await runtime.wait(run_id)
    via_runner = await PregelRunner(_graph(), clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert via_runtime.model_dump_json() == via_runner.model_dump_json()
