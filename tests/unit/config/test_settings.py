"""Unit tests for the minimal Phase-0 Settings object (spec 08 §1; ADR 0009)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.config import Settings

_ENV_VARS = ("MOCK_LLM", "KORCH_RUNTIME", "PERSISTENCE_BACKEND")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the recognised variables so each test controls the environment."""
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_describe_a_zero_config_local_run() -> None:
    settings = Settings()
    assert settings.mock_llm is True
    assert settings.korch_runtime == "local"
    assert settings.persistence_backend == "memory"


def test_bare_construction_ignores_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A key property of ADR 0009: Settings() is pure; only from_env() reads os.environ.
    monkeypatch.setenv("KORCH_RUNTIME", "temporal")
    assert Settings().korch_runtime == "local"


def test_from_env_reads_recognised_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KORCH_RUNTIME", "temporal")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "none")
    monkeypatch.setenv("MOCK_LLM", "false")
    settings = Settings.from_env()
    assert settings.korch_runtime == "temporal"
    assert settings.persistence_backend == "none"
    assert settings.mock_llm is False


def test_from_env_argument_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KORCH_RUNTIME", "temporal")
    assert Settings.from_env(korch_runtime="local").korch_runtime == "local"


def test_from_env_falls_back_to_defaults_when_unset() -> None:
    settings = Settings.from_env()
    assert settings.korch_runtime == "local"
    assert settings.persistence_backend == "memory"
    assert settings.mock_llm is True


def test_from_env_ignores_unrelated_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KORCH_TOTALLY_UNKNOWN", "1")
    assert Settings.from_env().korch_runtime == "local"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("korch_runtime", "distributed"),
        ("persistence_backend", "postgres"),
    ],
)
def test_invalid_enum_value_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_from_env_rejects_an_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KORCH_RUNTIME", "distributed")
    with pytest.raises(ValidationError):
        Settings.from_env()


def test_unknown_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        Settings(unknown_field=True)


def test_settings_is_immutable() -> None:
    settings = Settings()
    with pytest.raises(ValidationError):
        settings.korch_runtime = "temporal"  # type: ignore[misc]
