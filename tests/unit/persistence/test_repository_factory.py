"""Unit tests for resolve_repository (spec 05 §1, P7.5)."""

from __future__ import annotations

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError
from korchestrator.persistence import InMemoryGraphRepository, resolve_repository


def test_none_backend_runs_fully_standalone() -> None:
    assert resolve_repository(Settings(persistence_backend="none")) is None


def test_memory_backend_returns_an_in_memory_repository() -> None:
    repo = resolve_repository(Settings(persistence_backend="memory"))
    assert isinstance(repo, InMemoryGraphRepository)


def test_the_default_backend_is_memory() -> None:
    assert isinstance(resolve_repository(Settings()), InMemoryGraphRepository)


def test_an_injected_repository_wins_over_settings() -> None:
    injected = InMemoryGraphRepository()
    assert resolve_repository(Settings(persistence_backend="none"), injected) is injected


def test_kcg_backend_is_not_yet_implemented() -> None:
    with pytest.raises(ConfigurationError) as info:
        resolve_repository(Settings(persistence_backend="kcg"))
    assert info.value.code == "KORCH_CONFIG_INVALID"


def test_each_call_without_injection_builds_a_fresh_repository() -> None:
    settings = Settings(persistence_backend="memory")
    assert resolve_repository(settings) is not resolve_repository(settings)
