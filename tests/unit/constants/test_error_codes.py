"""Snapshot of the stable error-code strings (spec 08 §2.1, compatibility surface).

A code is never renamed or reused within a major version. Changing a value here is a breaking
change: it requires an ADR, a CHANGELOG entry, and a version decision in the same PR.
"""

from __future__ import annotations

from korchestrator.constants import error_codes

EXPECTED_CODES = {
    "KORCH_ERROR": "KORCH_ERROR",
    "KORCH_CONFIG_INVALID": "KORCH_CONFIG_INVALID",
    "KORCH_VALIDATION_FAILED": "KORCH_VALIDATION_FAILED",
    "KORCH_AUTH_FAILED": "KORCH_AUTH_FAILED",
    "KORCH_AUTH_FORBIDDEN": "KORCH_AUTH_FORBIDDEN",
    "KORCH_NETWORK_UNAVAILABLE": "KORCH_NETWORK_UNAVAILABLE",
    "KORCH_TIMEOUT": "KORCH_TIMEOUT",
    "KORCH_RATE_LIMITED": "KORCH_RATE_LIMITED",
    "KORCH_QUOTA_EXCEEDED": "KORCH_QUOTA_EXCEEDED",
    "KORCH_PROVIDER_FAILED": "KORCH_PROVIDER_FAILED",
    "KORCH_ROUTING_FAILED": "KORCH_ROUTING_FAILED",
    "ROUTING_NO_CANDIDATES": "ROUTING_NO_CANDIDATES",
    "TOOL_NOT_FOUND": "TOOL_NOT_FOUND",
    "TOOL_ACCESS_DENIED": "TOOL_ACCESS_DENIED",
    "TOOL_EXECUTION_FAILED": "TOOL_EXECUTION_FAILED",
    "NOT_IMPLEMENTED": "NOT_IMPLEMENTED",
    "KORCH_GOVERNANCE_HALT": "KORCH_GOVERNANCE_HALT",
    "KORCH_RUN_FAILED": "KORCH_RUN_FAILED",
    "KORCH_RUN_TIMEOUT": "KORCH_RUN_TIMEOUT",
    "KORCH_MISSING_EXTRA": "KORCH_MISSING_EXTRA",
    "KORCH_API_ERROR": "KORCH_API_ERROR",
}


def test_error_code_values_are_stable() -> None:
    actual = {name: getattr(error_codes, name) for name in EXPECTED_CODES}
    assert actual == EXPECTED_CODES


def test_public_codes_are_exported() -> None:
    # __all__ lists exactly the codes we snapshot — no more, no fewer.
    assert set(error_codes.__all__) == set(EXPECTED_CODES)
