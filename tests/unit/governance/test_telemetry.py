"""Unit tests for ``ControlTowerTelemetry`` (spec 05 §3.1, P7.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from korchestrator.governance import ControlTowerTelemetry

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def test_telemetry_round_trips_its_fields() -> None:
    telemetry = ControlTowerTelemetry(
        run_id="r1",
        tenant_id="acme",
        superstep=2,
        trust_score=0.75,
        active_agent_ids=("lead", "worker"),
        valid_time=NOW,
    )
    assert telemetry.run_id == "r1"
    assert telemetry.tenant_id == "acme"
    assert telemetry.superstep == 2
    assert telemetry.trust_score == 0.75
    assert telemetry.active_agent_ids == ("lead", "worker")
    assert telemetry.valid_time == NOW


def test_telemetry_defaults_to_no_active_agents() -> None:
    telemetry = ControlTowerTelemetry(
        run_id="r1", tenant_id="default", superstep=0, trust_score=1.0, valid_time=NOW
    )
    assert telemetry.active_agent_ids == ()


@pytest.mark.parametrize("trust_score", [-0.01, 1.01])
def test_telemetry_rejects_an_out_of_bounds_trust_score(trust_score: float) -> None:
    with pytest.raises(PydanticValidationError):
        ControlTowerTelemetry(
            run_id="r1", tenant_id="default", superstep=0, trust_score=trust_score, valid_time=NOW
        )


def test_telemetry_rejects_a_negative_superstep() -> None:
    with pytest.raises(PydanticValidationError):
        ControlTowerTelemetry(
            run_id="r1", tenant_id="default", superstep=-1, trust_score=1.0, valid_time=NOW
        )


def test_telemetry_is_frozen() -> None:
    telemetry = ControlTowerTelemetry(
        run_id="r1", tenant_id="default", superstep=0, trust_score=1.0, valid_time=NOW
    )
    with pytest.raises(PydanticValidationError):
        telemetry.trust_score = 0.5  # type: ignore[misc]
