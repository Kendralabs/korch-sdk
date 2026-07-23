"""Unit tests for TemporalRuntime's exception wrapping (spec 08 §2.2, P8.4).

Uses lightweight ``Client``/``WorkflowHandle`` mocks — no real Temporal server or
``WorkflowEnvironment`` needed — so these run in the standard suite, not only ``-m temporal``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

import pytest

pytest.importorskip("temporalio")

from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError, RPCStatusCode

from korchestrator.core import AgentGraph, Node
from korchestrator.exceptions import NetworkError, ProviderError, RunFailedError
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState
from korchestrator.runtime.temporal_runtime import TemporalRuntime

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _graph() -> AgentGraph:
    async def _noop(state: AgentState) -> object:
        raise NotImplementedError

    config = AgentConfig(id="a", persona=AgentPersona(role="r"))
    return AgentGraph([Node(config, _noop)])  # type: ignore[arg-type]


def _state() -> AgentState:
    return AgentState(run_id="r1", objective="summarize the quarterly report", transaction_time=NOW)


def _rpc_error() -> RPCError:
    return RPCError("server unavailable", RPCStatusCode.UNAVAILABLE, b"")


def _workflow_failure_error() -> WorkflowFailureError:
    return WorkflowFailureError(cause=ApplicationError("boom"))


# --- start() --------------------------------------------------------------------------------------


async def test_start_wraps_an_rpc_error_as_network_error() -> None:
    client = mock.AsyncMock()
    client.start_workflow.side_effect = _rpc_error()
    runtime = TemporalRuntime(_graph(), clock=lambda: NOW, client=client)
    with pytest.raises(NetworkError) as info:
        await runtime.start(_state())
    assert info.value.__cause__ is not None
    assert "r1" in info.value.message


async def test_start_wraps_a_generic_temporal_error_as_provider_error() -> None:
    client = mock.AsyncMock()
    client.start_workflow.side_effect = ApplicationError("rejected")
    runtime = TemporalRuntime(_graph(), clock=lambda: NOW, client=client)
    with pytest.raises(ProviderError) as info:
        await runtime.start(_state())
    assert info.value.__cause__ is not None


# --- wait() ---------------------------------------------------------------------------------------


async def test_wait_wraps_a_workflow_failure_error_as_run_failed_error() -> None:
    client = mock.Mock()
    handle = mock.AsyncMock()
    handle.result.side_effect = _workflow_failure_error()
    client.get_workflow_handle_for.return_value = handle
    runtime = TemporalRuntime(None, clock=lambda: NOW, client=client)
    with pytest.raises(RunFailedError) as info:
        await runtime.wait("r1")
    assert info.value.code == "KORCH_RUN_FAILED"
    assert info.value.__cause__ is not None


async def test_wait_wraps_an_rpc_error_as_network_error() -> None:
    client = mock.Mock()
    handle = mock.AsyncMock()
    handle.result.side_effect = _rpc_error()
    client.get_workflow_handle_for.return_value = handle
    runtime = TemporalRuntime(None, clock=lambda: NOW, client=client)
    with pytest.raises(NetworkError):
        await runtime.wait("r1")


# --- signal() -------------------------------------------------------------------------------------


async def test_signal_wraps_an_rpc_error_as_network_error() -> None:
    client = mock.Mock()
    handle = mock.AsyncMock()
    handle.signal.side_effect = _rpc_error()
    client.get_workflow_handle.return_value = handle
    runtime = TemporalRuntime(None, clock=lambda: NOW, client=client)
    with pytest.raises(NetworkError):
        await runtime.signal("r1", "cancel", {})


async def test_signal_wraps_a_generic_temporal_error_as_provider_error() -> None:
    client = mock.Mock()
    handle = mock.AsyncMock()
    handle.signal.side_effect = ApplicationError("no such run")
    client.get_workflow_handle.return_value = handle
    runtime = TemporalRuntime(None, clock=lambda: NOW, client=client)
    with pytest.raises(ProviderError) as info:
        await runtime.signal("r1", "pause", {})
    assert info.value.__cause__ is not None
