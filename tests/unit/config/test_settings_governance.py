"""Unit tests for the Phase-7 governance setting (spec 08 §1.3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.config import Settings

_GOVERNANCE_ENV = ("GOVERNANCE_TRUST_THRESHOLD",)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _GOVERNANCE_ENV:
        monkeypatch.delenv(name, raising=False)


def test_governance_trust_threshold_defaults_to_one_half() -> None:
    assert Settings().governance_trust_threshold == 0.5


def test_from_env_reads_governance_trust_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_TRUST_THRESHOLD", "0.75")
    assert Settings.from_env().governance_trust_threshold == 0.75


def test_from_env_argument_overrides_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_TRUST_THRESHOLD", "0.75")
    assert Settings.from_env(governance_trust_threshold=0.2).governance_trust_threshold == 0.2


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_governance_trust_threshold_is_bounded(value: float) -> None:
    with pytest.raises(ValidationError):
        Settings(governance_trust_threshold=value)
