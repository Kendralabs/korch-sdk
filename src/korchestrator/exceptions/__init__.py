"""Leaf-utility layer.

Allowed imports (beyond stdlib + pydantic): constants. Defines the whole KorchError tree; every
error the SDK raises deliberately is a KorchError subclass so consumers can catch one type.
"""

from korchestrator.exceptions.errors import (
    AuthError,
    ConfigurationError,
    GovernanceHaltError,
    KorchError,
    MissingExtraError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    RoutingError,
    RunFailedError,
    RunTimeoutError,
    TimeoutError,  # noqa: A004 — deliberately shadows the builtin (spec 08 §2.1)
    ToolError,
    ValidationError,
)

__all__ = [
    "AuthError",
    "ConfigurationError",
    "GovernanceHaltError",
    "KorchError",
    "MissingExtraError",
    "NetworkError",
    "ProviderError",
    "QuotaExceededError",
    "RateLimitError",
    "RoutingError",
    "RunFailedError",
    "RunTimeoutError",
    "TimeoutError",
    "ToolError",
    "ValidationError",
]
