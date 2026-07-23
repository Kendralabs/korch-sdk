"""Unit tests for the Settings object (spec 08 §1; ADR 0009, ADR 0016)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.config import Settings

_ENV_VARS = (
    "MOCK_LLM",
    "KORCH_RUNTIME",
    "PERSISTENCE_BACKEND",
    "KENDRA_AI_GATEWAY_URL",
    "LLM_GATEWAY_URL",
    "KENDRA_GATEWAY_API_KEY",
    "KORCH_MAX_SUPERSTEPS",
    "KORCH_PLUGINS_ENABLED",
    "KORCH_LOG_LEVEL",
    "KORCH_TELEMETRY_ENABLED",
    "KORCH_ENGINE_URL",
    "KORCH_ENGINE_API_KEY",
    "KORCH_ENGINE_NAMESPACE",
    "KORCH_ENGINE_TASK_QUEUE",
    "TEMPORAL_ADDRESS",
    "TEMPORAL_NAMESPACE",
    "TEMPORAL_TASK_QUEUE",
    "TEMPORAL_API_KEY",
    "TEMPORAL_HITL_TIMEOUT_SECONDS",
)


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


# --- the full P8.1 variable table (spec 08 §1.3) -------------------------------------------------


def test_new_fields_have_the_documented_defaults() -> None:
    settings = Settings()
    assert settings.kendra_ai_gateway_url is None
    assert settings.kendra_gateway_api_key is None
    assert settings.korch_max_supersteps == 10
    assert settings.korch_plugins_enabled is False
    assert settings.korch_log_level == "WARNING"
    assert settings.korch_telemetry_enabled is False
    assert settings.korch_engine_url is None
    assert settings.korch_engine_namespace == "default"
    assert settings.korch_engine_task_queue == "korchestrator"
    assert settings.temporal_address == "localhost:7233"
    assert settings.temporal_namespace == "default"
    assert settings.temporal_task_queue == "korchestrator"
    assert settings.temporal_api_key is None
    assert settings.temporal_hitl_timeout_seconds == 86400


def test_from_env_reads_the_new_scalar_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KENDRA_AI_GATEWAY_URL", "https://gateway.example.com")
    monkeypatch.setenv("KORCH_MAX_SUPERSTEPS", "25")
    monkeypatch.setenv("KORCH_PLUGINS_ENABLED", "true")
    monkeypatch.setenv("KORCH_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("TEMPORAL_ADDRESS", "temporal.internal:7233")
    monkeypatch.setenv("TEMPORAL_HITL_TIMEOUT_SECONDS", "3600")
    settings = Settings.from_env()
    assert settings.kendra_ai_gateway_url == "https://gateway.example.com"
    assert settings.korch_max_supersteps == 25
    assert settings.korch_plugins_enabled is True
    assert settings.korch_log_level == "DEBUG"
    assert settings.temporal_address == "temporal.internal:7233"
    assert settings.temporal_hitl_timeout_seconds == 3600


def test_korch_max_supersteps_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Settings(korch_max_supersteps=0)
    with pytest.raises(ValidationError):
        Settings(korch_max_supersteps=101)


# --- secrets (SecretStr) --------------------------------------------------------------------------


def test_secret_fields_are_not_exposed_in_repr() -> None:
    settings = Settings(kendra_gateway_api_key="sk-super-secret-value")
    assert "sk-super-secret-value" not in repr(settings)
    assert "sk-super-secret-value" not in str(settings)


def test_secret_field_value_is_recoverable_via_get_secret_value() -> None:
    settings = Settings(kendra_gateway_api_key="sk-super-secret-value")
    assert settings.kendra_gateway_api_key is not None
    assert settings.kendra_gateway_api_key.get_secret_value() == "sk-super-secret-value"


def test_from_env_reads_secret_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KENDRA_GATEWAY_API_KEY", "sk-from-env")
    settings = Settings.from_env()
    assert settings.kendra_gateway_api_key is not None
    assert settings.kendra_gateway_api_key.get_secret_value() == "sk-from-env"


# --- MOCK_LLM's environment-aware default (spec 08 §1.3) -----------------------------------------


def test_bare_construction_always_defaults_mock_llm_true() -> None:
    # Bare Settings() is pure and never inspects other fields for its default (ADR 0009).
    assert Settings(kendra_gateway_api_key="sk-x").mock_llm is True


def test_from_env_defaults_mock_llm_false_when_a_gateway_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KENDRA_GATEWAY_API_KEY", "sk-present")
    assert Settings.from_env().mock_llm is False


def test_from_env_defaults_mock_llm_true_when_no_gateway_key_is_present() -> None:
    assert Settings.from_env().mock_llm is True


def test_an_explicit_mock_llm_override_wins_over_the_gateway_key_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KENDRA_GATEWAY_API_KEY", "sk-present")
    assert Settings.from_env(mock_llm=True).mock_llm is True


def test_an_explicit_mock_llm_env_var_wins_over_the_gateway_key_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KENDRA_GATEWAY_API_KEY", "sk-present")
    monkeypatch.setenv("MOCK_LLM", "true")
    assert Settings.from_env().mock_llm is True


# --- LLM_GATEWAY_URL alias (spec 08 §1.3) ---------------------------------------------------------


def test_llm_gateway_url_is_a_fallback_name_for_kendra_ai_gateway_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_GATEWAY_URL", "https://fallback.example.com")
    assert Settings.from_env().kendra_ai_gateway_url == "https://fallback.example.com"


def test_kendra_ai_gateway_url_takes_precedence_over_the_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KENDRA_AI_GATEWAY_URL", "https://primary.example.com")
    monkeypatch.setenv("LLM_GATEWAY_URL", "https://fallback.example.com")
    assert Settings.from_env().kendra_ai_gateway_url == "https://primary.example.com"
