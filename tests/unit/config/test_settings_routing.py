"""Unit tests for the Phase-5 routing settings and their env parsing (spec 08 §1)."""

from __future__ import annotations

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError

_ROUTING_ENV = (
    "ROUTING_STRATEGY",
    "AGENT_MODEL_MAP",
    "ROUTING_WEIGHTS",
    "ROUTING_PRIORITY_ORDER",
    "EMBEDDING_PROVIDER",
    "MODELCARD_SOURCE",
    "MODELCARD_PATH",
    "MODELCARD_URL",
    "MODELCARD_CACHE_TTL_SECONDS",
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ROUTING_ENV:
        monkeypatch.delenv(name, raising=False)


def test_routing_defaults() -> None:
    settings = Settings()
    assert settings.routing_strategy == "explicit"
    assert settings.agent_model_map == {}
    assert settings.routing_weights == {"quality": 0.5, "cost": 0.3, "latency": 0.2}
    assert settings.routing_priority_order == ("explicit", "algorithmic", "fallback")
    assert settings.modelcard_source == "builtin"
    assert settings.modelcard_cache_ttl_seconds == 900


def test_default_agent_model_map_is_not_shared_between_instances() -> None:
    # Field(default_factory=dict) gives each instance its own map (no mutable-default aliasing).
    assert Settings().agent_model_map is not Settings().agent_model_map


def test_from_env_parses_scalar_json_and_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTING_STRATEGY", "algorithmic")
    monkeypatch.setenv("AGENT_MODEL_MAP", '{"lead": "gpt-4o", "worker": "gpt-4o-mini"}')
    monkeypatch.setenv("ROUTING_PRIORITY_ORDER", "explicit, algorithmic, fallback")
    monkeypatch.setenv("MODELCARD_CACHE_TTL_SECONDS", "120")
    settings = Settings.from_env()
    assert settings.routing_strategy == "algorithmic"
    assert settings.agent_model_map == {"lead": "gpt-4o", "worker": "gpt-4o-mini"}
    assert settings.routing_priority_order == ("explicit", "algorithmic", "fallback")
    assert settings.modelcard_cache_ttl_seconds == 120


def test_from_env_bad_json_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_MODEL_MAP", "{not json}")
    with pytest.raises(ConfigurationError) as info:
        Settings.from_env()
    assert "AGENT_MODEL_MAP" in info.value.message


def test_invalid_strategy_is_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(routing_strategy="sematic")  # type: ignore[arg-type]
