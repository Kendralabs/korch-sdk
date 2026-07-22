"""Unit tests for governance trust scoring (spec 05 §3.1, spec 06 §7, P7.2)."""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.governance import ControlTowerTelemetry, check_governance, derive_telemetry
from korchestrator.models.state import AgentState, Message

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _msg(sender: str, superstep: int) -> Message:
    return Message(
        id=f"r:{superstep}:{sender}:0",
        sender=sender,
        content="hi",
        kind="answer",
        superstep=superstep,
        valid_time=NOW,
    )


def _state(**overrides: object) -> AgentState:
    base: dict[str, object] = {
        "run_id": "r1",
        "objective": "summarize the quarterly report",
        "transaction_time": NOW,
    }
    base.update(overrides)
    return AgentState(**base)  # type: ignore[arg-type]


def test_derive_telemetry_on_a_fresh_state_has_no_active_agents() -> None:
    telemetry = derive_telemetry(_state())
    assert telemetry.superstep == 0
    assert telemetry.active_agent_ids == ()
    assert telemetry.trust_score == 1.0
    assert telemetry.run_id == "r1"
    assert telemetry.tenant_id == "default"
    assert telemetry.valid_time == NOW


def test_derive_telemetry_reads_the_just_completed_superstep() -> None:
    # superstep has already advanced to 2 by the time this state is observed; the messages that
    # matter are the ones stamped with superstep 1, the round that just completed.
    state = _state(
        superstep=2,
        trust_score=0.6,
        messages=(_msg("lead", 0), _msg("worker", 1), _msg("reviewer", 1)),
    )
    telemetry = derive_telemetry(state)
    assert telemetry.superstep == 1
    assert telemetry.active_agent_ids == ("reviewer", "worker")
    assert telemetry.trust_score == 0.6


def test_derive_telemetry_dedupes_and_sorts_active_agents() -> None:
    state = _state(superstep=1, messages=(_msg("b", 0), _msg("a", 0), _msg("a", 0)))
    assert derive_telemetry(state).active_agent_ids == ("a", "b")


def test_check_governance_reads_the_kernels_trust_score_unchanged() -> None:
    state = _state(superstep=3, trust_score=0.42)
    result = check_governance(state)
    assert result.trust_score == 0.42
    assert result.telemetry.trust_score == 0.42
    assert isinstance(result.telemetry, ControlTowerTelemetry)


def test_check_governance_is_pure_and_repeatable() -> None:
    state = _state(superstep=2, trust_score=0.75, messages=(_msg("worker", 1),))
    first = check_governance(state)
    second = check_governance(state)
    assert first == second
