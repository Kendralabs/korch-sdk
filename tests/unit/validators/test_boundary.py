"""Unit tests for trust-boundary validation (spec 08 §7, P8.6)."""

from __future__ import annotations

import pytest

from korchestrator.exceptions import ValidationError
from korchestrator.validators import (
    validate_max_supersteps,
    validate_objective,
    validate_unique_agent_id,
)


def test_validate_objective_accepts_a_long_enough_objective() -> None:
    validate_objective("Summarize the quarterly incident reports")  # no error


def test_validate_objective_rejects_a_short_objective() -> None:
    with pytest.raises(ValidationError) as info:
        validate_objective("too short")
    assert info.value.code == "KORCH_VALIDATION_FAILED"


def test_validate_objective_boundary_is_inclusive() -> None:
    validate_objective("1234567890")  # exactly 10 characters, no error
    with pytest.raises(ValidationError):
        validate_objective("123456789")  # 9 characters


@pytest.mark.parametrize("value", [1, 10, 100])
def test_validate_max_supersteps_accepts_the_documented_range(value: int) -> None:
    validate_max_supersteps(value)  # no error


@pytest.mark.parametrize("value", [0, -1, 101, 1000])
def test_validate_max_supersteps_rejects_outside_the_range(value: int) -> None:
    with pytest.raises(ValidationError):
        validate_max_supersteps(value)


def test_validate_unique_agent_id_accepts_a_new_id() -> None:
    validate_unique_agent_id("lead", {"security", "perf"})  # no error


def test_validate_unique_agent_id_rejects_a_duplicate() -> None:
    with pytest.raises(ValidationError) as info:
        validate_unique_agent_id("lead", {"lead", "perf"})
    assert "lead" in str(info.value)
    assert info.value.code == "KORCH_VALIDATION_FAILED"
