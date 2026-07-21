"""Contract tests for models/result.py (P1.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState, RunStatus

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)
_STATE = AgentState(run_id="r", objective="summarize the report", transaction_time=NOW)


def _result(**overrides: object) -> RunResult:
    base: dict[str, object] = {
        "run_id": "r",
        "status": RunStatus.COMPLETED,
        "final_answer": "the summary",
        "supersteps": 3,
        "state": _STATE,
        "trust_score": 0.9,
        "started_at": NOW,
    }
    base.update(overrides)
    return RunResult(**base)  # type: ignore[arg-type]


def test_run_result_defaults() -> None:
    result = _result()
    assert result.schema_version == 1
    assert result.messages == ()
    assert result.error_code is None
    assert result.error is None
    assert result.completed_at is None


def test_run_result_supersteps_non_negative() -> None:
    with pytest.raises(ValidationError):
        _result(supersteps=-1)


def test_run_result_trust_score_bounds() -> None:
    with pytest.raises(ValidationError):
        _result(trust_score=1.2)


def test_run_result_status_is_a_run_status() -> None:
    assert _result(status=RunStatus.FAILED).status is RunStatus.FAILED


def test_run_result_is_frozen() -> None:
    result = _result()
    with pytest.raises(ValidationError):
        result.final_answer = "changed"  # type: ignore[misc]
