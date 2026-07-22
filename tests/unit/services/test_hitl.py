"""Unit tests for the HITL control-signal façade methods (P7.4, spec 06 §7).

These exercise ``Korch``/``Swarm``'s ``pause``/``resume``/``cancel``/``edit_resume`` against an
injected fake runtime — no Temporal server, no ``[temporal]`` extra needed. The real Temporal wiring
(auto-pause on low trust, ``edit_resume`` applying through the workflow) is covered by
``tests/integration/test_temporal_runtime.py``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone

import pytest

from korchestrator import Korch, Swarm
from korchestrator.config import Settings
from korchestrator.exceptions import MissingExtraError
from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState
from korchestrator.services import _composition as comp
from korchestrator.types import JSONValue

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


class _FakeSignalRuntime:
    """A minimal ``IDurableRuntime`` double that only records delivered signals."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def now(self) -> datetime:
        return NOW

    async def start(self, state: AgentState, *, max_supersteps: int = 10) -> str:
        raise NotImplementedError

    async def wait(self, run_id: str, *, timeout_seconds: float | None = None) -> RunResult:
        raise NotImplementedError

    async def signal(self, run_id: str, name: str, payload: Mapping[str, str]) -> None:
        self.calls.append((run_id, name, dict(payload)))


# --- send_control_signal (services/_composition.py) --------------------------------------------


async def test_send_control_signal_uses_the_injected_runtime_directly() -> None:
    runtime = _FakeSignalRuntime()
    await comp.send_control_signal(
        Settings(),
        "run-1",
        "pause",
        runtime=runtime,  # type: ignore[arg-type]
    )
    assert runtime.calls == [("run-1", "pause", {})]


async def test_send_control_signal_encodes_edit_resume_as_json() -> None:
    runtime = _FakeSignalRuntime()
    await comp.send_control_signal(
        Settings(),
        "run-1",
        "edit_resume",
        runtime=runtime,  # type: ignore[arg-type]
        updates={"note": "reviewed"},
        trust_delta=0.2,
    )
    [(run_id, name, payload)] = runtime.calls
    assert (run_id, name) == ("run-1", "edit_resume")
    body = json.loads(payload["state_update"])
    assert body == {"updates": {"note": "reviewed"}, "trust_delta": 0.2}


async def test_send_control_signal_ignores_edit_resume_fields_for_other_signals() -> None:
    runtime = _FakeSignalRuntime()
    await comp.send_control_signal(
        Settings(),
        "run-1",
        "resume",
        runtime=runtime,  # type: ignore[arg-type]
        updates={"note": "ignored"},
    )
    assert runtime.calls == [("run-1", "resume", {})]


async def test_send_control_signal_on_the_local_runtime_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await comp.send_control_signal(Settings(korch_runtime="local"), "run-1", "cancel")


async def test_send_control_signal_selecting_temporal_needs_the_extra_or_a_client() -> None:
    import importlib.util

    from korchestrator.exceptions import ConfigurationError

    if importlib.util.find_spec("temporalio") is None:
        # Without the extra, selecting temporal is an actionable missing-extra error.
        with pytest.raises(MissingExtraError) as info:
            await comp.send_control_signal(Settings(korch_runtime="temporal"), "run-1", "pause")
        assert info.value.code == "KORCH_MISSING_EXTRA"
    else:
        # With the extra installed but no client injected, it's a graph-less TemporalRuntime with
        # no client — the same actionable error TemporalRuntime.signal() already raises.
        with pytest.raises(ConfigurationError):
            await comp.send_control_signal(Settings(korch_runtime="temporal"), "run-1", "pause")


# --- Korch/Swarm façade methods ------------------------------------------------------------------


def test_korch_pause_delegates_to_the_injected_runtime() -> None:
    runtime = _FakeSignalRuntime()
    Korch(runtime=runtime).pause("run-1")  # type: ignore[arg-type]
    assert runtime.calls == [("run-1", "pause", {})]


def test_korch_resume_delegates_to_the_injected_runtime() -> None:
    runtime = _FakeSignalRuntime()
    Korch(runtime=runtime).resume("run-1")  # type: ignore[arg-type]
    assert runtime.calls == [("run-1", "resume", {})]


def test_korch_cancel_delegates_to_the_injected_runtime() -> None:
    runtime = _FakeSignalRuntime()
    Korch(runtime=runtime).cancel("run-1")  # type: ignore[arg-type]
    assert runtime.calls == [("run-1", "cancel", {})]


def test_korch_edit_resume_delegates_with_the_encoded_payload() -> None:
    runtime = _FakeSignalRuntime()
    updates: dict[str, JSONValue] = {"decision": "approved"}
    Korch(runtime=runtime).edit_resume("run-1", updates=updates, trust_delta=0.1)  # type: ignore[arg-type]
    [(run_id, name, payload)] = runtime.calls
    assert (run_id, name) == ("run-1", "edit_resume")
    assert json.loads(payload["state_update"]) == {"updates": updates, "trust_delta": 0.1}


def test_korch_pause_on_the_default_local_settings_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        Korch(settings=Settings(korch_runtime="local")).pause("run-1")


def test_swarm_pause_delegates_to_the_injected_runtime() -> None:
    runtime = _FakeSignalRuntime()
    Swarm(objective="Review this PR for security", runtime=runtime).pause(  # type: ignore[arg-type]
        "run-1"
    )
    assert runtime.calls == [("run-1", "pause", {})]


def test_swarm_edit_resume_delegates_with_the_encoded_payload() -> None:
    runtime = _FakeSignalRuntime()
    swarm = Swarm(objective="Review this PR for security", runtime=runtime)  # type: ignore[arg-type]
    swarm.edit_resume("run-1", trust_delta=-0.1)
    [(run_id, name, payload)] = runtime.calls
    assert (run_id, name) == ("run-1", "edit_resume")
    assert json.loads(payload["state_update"]) == {"updates": {}, "trust_delta": -0.1}


def test_swarm_cancel_on_the_default_local_settings_raises_not_implemented() -> None:
    swarm = Swarm(objective="Review this PR for security", settings=Settings(korch_runtime="local"))
    with pytest.raises(NotImplementedError):
        swarm.cancel("run-1")
