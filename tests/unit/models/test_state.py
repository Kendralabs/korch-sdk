"""Contract tests for models/state.py (P1.2 — fields are the contract)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from korchestrator.models.state import (
    AgentState,
    Message,
    MessageRole,
    Performative,
    RunStatus,
    StateUpdate,
)

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


def _message(**overrides: object) -> Message:
    base: dict[str, object] = {
        "id": "run:0:agent:0",
        "sender": "agent",
        "content": "hello",
        "superstep": 0,
        "valid_time": NOW,
    }
    base.update(overrides)
    return Message(**base)  # type: ignore[arg-type]


def test_message_defaults() -> None:
    msg = _message()
    assert msg.role is MessageRole.ASSISTANT
    assert msg.performative is Performative.INFORM
    assert msg.kind == "thought"
    assert msg.recipient is None
    assert msg.metadata == {}


def test_message_is_frozen_and_forbids_extra() -> None:
    msg = _message()
    with pytest.raises(ValidationError):
        msg.content = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _message(unexpected="x")


def test_message_superstep_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        _message(superstep=-1)


def test_message_metadata_accepts_nested_json() -> None:
    msg = _message(metadata={"scores": [1, 2, {"final": True}], "note": None})
    assert msg.metadata["scores"] == [1, 2, {"final": True}]


def test_state_update_defaults_and_trust_delta_bounds() -> None:
    update = StateUpdate(agent_id="a", valid_time=NOW)
    assert update.halt is False
    assert update.trust_delta == 0.0
    assert update.messages == ()
    with pytest.raises(ValidationError):
        StateUpdate(agent_id="a", valid_time=NOW, trust_delta=1.5)
    with pytest.raises(ValidationError):
        StateUpdate(agent_id="a", valid_time=NOW, trust_delta=-1.5)


def test_agent_state_defaults() -> None:
    state = AgentState(run_id="r", objective="summarize the report", transaction_time=NOW)
    assert state.tenant_id == "default"
    assert state.status is RunStatus.STARTED
    assert state.superstep == 0
    assert state.halted is False
    assert state.trust_score == 1.0
    assert state.schema_version == 1


def test_agent_state_objective_minimum_length() -> None:
    with pytest.raises(ValidationError):
        AgentState(run_id="r", objective="too short", transaction_time=NOW)


def test_agent_state_trust_score_bounds() -> None:
    with pytest.raises(ValidationError):
        AgentState(
            run_id="r", objective="summarize the report", transaction_time=NOW, trust_score=1.1
        )


def test_run_status_vocabulary_is_complete() -> None:
    assert {status.value for status in RunStatus} == {
        "started",
        "running",
        "governance_paused",
        "completed",
        "failed",
        "cancelled",
        "timed_out",
    }
