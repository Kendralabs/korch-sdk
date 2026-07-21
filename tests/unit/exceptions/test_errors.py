"""Unit tests for the KorchError hierarchy (spec 08 §2, P1.1)."""

from __future__ import annotations

import builtins

import pytest

from korchestrator import exceptions as exc
from korchestrator.exceptions import (
    KorchError,
    ProviderError,
    TimeoutError,  # noqa: A004 — deliberately shadows the builtin (spec 08 §2.1)
    ToolError,
    ValidationError,
)

EXPECTED_DEFAULT_CODES = {
    "KorchError": "KORCH_ERROR",
    "ConfigurationError": "KORCH_CONFIG_INVALID",
    "ValidationError": "KORCH_VALIDATION_FAILED",
    "AuthError": "KORCH_AUTH_FAILED",
    "NetworkError": "KORCH_NETWORK_UNAVAILABLE",
    "TimeoutError": "KORCH_TIMEOUT",
    "RateLimitError": "KORCH_RATE_LIMITED",
    "QuotaExceededError": "KORCH_QUOTA_EXCEEDED",
    "ProviderError": "KORCH_PROVIDER_FAILED",
    "RoutingError": "KORCH_ROUTING_FAILED",
    "ToolError": "TOOL_NOT_FOUND",
    "GovernanceHaltError": "KORCH_GOVERNANCE_HALT",
    "RunFailedError": "KORCH_RUN_FAILED",
    "RunTimeoutError": "KORCH_RUN_TIMEOUT",
    "MissingExtraError": "KORCH_MISSING_EXTRA",
}


def test_all_exports_are_accounted_for() -> None:
    # The public surface of this module is exactly the hierarchy we expect.
    assert set(exc.__all__) == set(EXPECTED_DEFAULT_CODES)


@pytest.mark.parametrize("name", sorted(EXPECTED_DEFAULT_CODES))
def test_every_error_is_a_korcherror_subclass(name: str) -> None:
    cls = getattr(exc, name)
    assert issubclass(cls, KorchError)


@pytest.mark.parametrize(("name", "code"), sorted(EXPECTED_DEFAULT_CODES.items()))
def test_default_code_matches(name: str, code: str) -> None:
    cls = getattr(exc, name)
    assert cls("something went wrong").code == code


def test_base_stores_message_code_and_context() -> None:
    err = KorchError("gateway failed", code="KORCH_PROVIDER_FAILED", model="gpt-4o-mini")
    assert err.message == "gateway failed"
    assert str(err) == "gateway failed"
    assert err.code == "KORCH_PROVIDER_FAILED"
    assert err.context == {"model": "gpt-4o-mini"}


def test_context_is_empty_by_default() -> None:
    assert ValidationError("bad input").context == {}


def test_explicit_code_overrides_the_default() -> None:
    assert ValidationError("bad", code="CUSTOM_CODE").code == "CUSTOM_CODE"


def test_tool_error_carries_a_specific_code() -> None:
    err = ToolError("tool 'crm.lookup' is not mounted", code="TOOL_ACCESS_DENIED")
    assert err.code == "TOOL_ACCESS_DENIED"
    assert isinstance(err, KorchError)


def test_korch_timeout_error_shadows_but_is_not_the_builtin() -> None:
    assert issubclass(TimeoutError, KorchError)
    assert not issubclass(TimeoutError, builtins.TimeoutError)


def test_catching_the_base_catches_a_subclass() -> None:
    with pytest.raises(KorchError) as info:
        raise ProviderError("upstream 500")
    assert info.value.code == "KORCH_PROVIDER_FAILED"


def test_wrapping_preserves_the_cause() -> None:
    original = ValueError("raw driver error")
    try:
        try:
            raise original
        except ValueError as cause:
            raise ProviderError("gateway call failed") from cause
    except ProviderError as wrapped:
        assert wrapped.__cause__ is original
