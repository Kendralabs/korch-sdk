"""Leaf-utility layer. Imports: stdlib only.

Stable string codes carried by every :class:`~korchestrator.exceptions.KorchError`. These
codes are part of the compatibility surface (spec 08 §2.1): a code is never renamed or reused
within a major version. New codes may be added; existing ones are frozen.
"""

from __future__ import annotations

# --- base -----------------------------------------------------------------------------------
KORCH_ERROR = "KORCH_ERROR"

# --- configuration & validation -------------------------------------------------------------
KORCH_CONFIG_INVALID = "KORCH_CONFIG_INVALID"
KORCH_VALIDATION_FAILED = "KORCH_VALIDATION_FAILED"

# --- identity & authorization ---------------------------------------------------------------
KORCH_AUTH_FAILED = "KORCH_AUTH_FAILED"
KORCH_AUTH_FORBIDDEN = "KORCH_AUTH_FORBIDDEN"

# --- transport & providers ------------------------------------------------------------------
KORCH_NETWORK_UNAVAILABLE = "KORCH_NETWORK_UNAVAILABLE"
KORCH_TIMEOUT = "KORCH_TIMEOUT"
KORCH_RATE_LIMITED = "KORCH_RATE_LIMITED"
KORCH_QUOTA_EXCEEDED = "KORCH_QUOTA_EXCEEDED"
KORCH_PROVIDER_FAILED = "KORCH_PROVIDER_FAILED"

# --- routing --------------------------------------------------------------------------------
KORCH_ROUTING_FAILED = "KORCH_ROUTING_FAILED"
ROUTING_NO_CANDIDATES = "ROUTING_NO_CANDIDATES"

# --- tools ----------------------------------------------------------------------------------
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
TOOL_ACCESS_DENIED = "TOOL_ACCESS_DENIED"
TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

# --- governance & run lifecycle -------------------------------------------------------------
KORCH_GOVERNANCE_HALT = "KORCH_GOVERNANCE_HALT"
KORCH_RUN_FAILED = "KORCH_RUN_FAILED"
KORCH_RUN_TIMEOUT = "KORCH_RUN_TIMEOUT"

# --- optional dependencies ------------------------------------------------------------------
# Not in the spec 08 §2.1 tree, but required by the optional-dependency contract
# (.claude/rules/architecture-boundaries.md) that MissingExtraError implements.
KORCH_MISSING_EXTRA = "KORCH_MISSING_EXTRA"

# --- remote client ----------------------------------------------------------------------------
# Not in the spec 08 §2.1 tree either; required by the remote contract (spec 04 §7.5), which
# names ApiError explicitly as the one error type for a failed KorchestratorClient call.
KORCH_API_ERROR = "KORCH_API_ERROR"

__all__ = [
    "KORCH_API_ERROR",
    "KORCH_AUTH_FAILED",
    "KORCH_AUTH_FORBIDDEN",
    "KORCH_CONFIG_INVALID",
    "KORCH_ERROR",
    "KORCH_GOVERNANCE_HALT",
    "KORCH_MISSING_EXTRA",
    "KORCH_NETWORK_UNAVAILABLE",
    "KORCH_PROVIDER_FAILED",
    "KORCH_QUOTA_EXCEEDED",
    "KORCH_RATE_LIMITED",
    "KORCH_ROUTING_FAILED",
    "KORCH_RUN_FAILED",
    "KORCH_RUN_TIMEOUT",
    "KORCH_TIMEOUT",
    "KORCH_VALIDATION_FAILED",
    "NOT_IMPLEMENTED",
    "ROUTING_NO_CANDIDATES",
    "TOOL_ACCESS_DENIED",
    "TOOL_EXECUTION_FAILED",
    "TOOL_NOT_FOUND",
]
