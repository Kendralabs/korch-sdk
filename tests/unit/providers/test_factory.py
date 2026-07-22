"""Unit tests for the get_lm gateway factory (P4.3)."""

from __future__ import annotations

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError, ValidationError
from korchestrator.providers import MockLM, OpenAIGateway, get_lm


def test_default_settings_select_the_offline_mock() -> None:
    assert isinstance(get_lm("gpt-4o"), MockLM)


def test_empty_model_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        get_lm("")


def test_real_gateway_is_built_from_injected_credentials() -> None:
    gateway = get_lm(
        "gpt-4o",
        settings=Settings(mock_llm=False),
        api_key="sk-test",
        base_url="https://api.openai.test/v1",
    )
    assert isinstance(gateway, OpenAIGateway)
    assert gateway.base_url == "https://api.openai.test/v1"


def test_real_gateway_without_credentials_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        get_lm("gpt-4o", settings=Settings(mock_llm=False))
