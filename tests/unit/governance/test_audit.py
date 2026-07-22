"""Unit tests for the governance audit log (P7.3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from korchestrator.governance import AuditLog, check_governance, evaluate_policy
from korchestrator.models.state import AgentState

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)
LATER = datetime(2026, 7, 23, 0, 1, tzinfo=timezone.utc)


def _state(run_id: str, trust_score: float = 1.0) -> AgentState:
    return AgentState(
        run_id=run_id,
        objective="summarize the quarterly report",
        trust_score=trust_score,
        transaction_time=NOW,
    )


def test_a_fresh_log_has_no_entries() -> None:
    assert AuditLog().entries == ()


def test_record_appends_and_returns_the_entry() -> None:
    log = AuditLog()
    check = check_governance(_state("r1"))
    decision = evaluate_policy(check, agent_id="worker", hitl_threshold=None, global_threshold=0.5)
    entry = log.record(check.telemetry, decision, recorded_at=NOW)
    assert log.entries == (entry,)
    assert entry.telemetry == check.telemetry
    assert entry.decision == decision
    assert entry.recorded_at == NOW


def test_entries_preserve_recording_order() -> None:
    log = AuditLog()
    check = check_governance(_state("r1"))
    decision = evaluate_policy(check, agent_id="worker", hitl_threshold=None, global_threshold=0.5)
    first = log.record(check.telemetry, decision, recorded_at=NOW)
    second = log.record(check.telemetry, decision, recorded_at=LATER)
    assert log.entries == (first, second)


def test_for_run_filters_by_run_id() -> None:
    log = AuditLog()
    check_r1 = check_governance(_state("r1"))
    check_r2 = check_governance(_state("r2"))
    decision = evaluate_policy(
        check_r1, agent_id="worker", hitl_threshold=None, global_threshold=0.5
    )
    entry_r1 = log.record(check_r1.telemetry, decision, recorded_at=NOW)
    log.record(check_r2.telemetry, decision, recorded_at=NOW)
    assert log.for_run("r1") == (entry_r1,)


def test_the_entry_is_frozen() -> None:
    log = AuditLog()
    check = check_governance(_state("r1"))
    decision = evaluate_policy(check, agent_id="worker", hitl_threshold=None, global_threshold=0.5)
    entry = log.record(check.telemetry, decision, recorded_at=NOW)
    with pytest.raises(ValidationError):
        entry.recorded_at = LATER  # type: ignore[misc]
