"""Leaf-utility layer. Imports: korchestrator.constants, stdlib.

The whole ``KorchError`` tree (spec 08 §2). Every error the SDK raises descends from
``KorchError``, so a consumer can catch one type. Raw ``temporalio`` / ``httpx`` / ``dspy`` /
driver exceptions are wrapped at the layer that owns them (``raise ... from exc``) and never
cross a module boundary.
"""

from __future__ import annotations

from korchestrator.constants import error_codes as codes

__all__ = [
    "ApiError",
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


class KorchError(Exception):
    """Base class for every error the SDK raises.

    Catching ``KorchError`` catches everything the SDK can raise deliberately. Each instance
    carries a stable ``code`` (from :mod:`korchestrator.constants.error_codes`, part of the
    compatibility surface) and an optional ``context`` mapping of tenant-safe string fields.

    Args:
        message: A human-readable, actionable message — what failed, which value was
            involved, and what to do. It MUST NOT contain secrets or a full prompt.
        code: The stable error code. Defaults to the class's ``default_code``.
        **context: Tenant-safe string fields describing the failure (e.g. ``model="gpt-4o"``).

    Example:
        >>> from korchestrator.exceptions import KorchError, ValidationError
        >>> err = ValidationError("Objective must be at least 10 characters.")
        >>> err.code
        'KORCH_VALIDATION_FAILED'
        >>> isinstance(err, KorchError)
        True
    """

    default_code: str = codes.KORCH_ERROR

    def __init__(self, message: str, *, code: str | None = None, **context: str) -> None:
        """Build the error with an actionable message, a stable code, and string context."""
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.context = context


class ConfigurationError(KorchError):
    """Configuration is invalid: a bad value, range, enum, or mutually exclusive setting."""

    default_code = codes.KORCH_CONFIG_INVALID


class ValidationError(KorchError):
    """Input failed validation at a trust boundary, before any effect took place."""

    default_code = codes.KORCH_VALIDATION_FAILED


class AuthError(KorchError):
    """Authentication failed or the caller is not authorized for the resource/tenant."""

    default_code = codes.KORCH_AUTH_FAILED


class NetworkError(KorchError):
    """A network dependency was unavailable or unreachable."""

    default_code = codes.KORCH_NETWORK_UNAVAILABLE


class TimeoutError(KorchError):  # noqa: A001 — deliberately shadows the builtin (spec 08 §2.1).
    """An operation exceeded its deadline.

    Deliberately shadows the builtin ``TimeoutError`` inside the package namespace; it subclasses
    ``KorchError`` only. Import it explicitly (``from korchestrator.exceptions import
    TimeoutError``) so the shadowing is visible at the import site.
    """

    default_code = codes.KORCH_TIMEOUT


class RateLimitError(KorchError):
    """A provider or gateway rate limit was hit."""

    default_code = codes.KORCH_RATE_LIMITED


class QuotaExceededError(KorchError):
    """A tenant or account quota was exhausted."""

    default_code = codes.KORCH_QUOTA_EXCEEDED


class ProviderError(KorchError):
    """An upstream model or service provider failed."""

    default_code = codes.KORCH_PROVIDER_FAILED


class RoutingError(KorchError):
    """No model could be selected for a task, or routing otherwise failed."""

    default_code = codes.KORCH_ROUTING_FAILED


class ToolError(KorchError):
    """A tool invocation failed, was not found, or was denied.

    The specific case is carried by ``code`` — ``TOOL_NOT_FOUND``, ``TOOL_ACCESS_DENIED``, or
    ``NOT_IMPLEMENTED`` — which callers pass explicitly.
    """

    default_code = codes.TOOL_NOT_FOUND


class GovernanceHaltError(KorchError):
    """Governance halted the run because trust fell below the configured threshold."""

    default_code = codes.KORCH_GOVERNANCE_HALT


class RunFailedError(KorchError):
    """A run terminated in a failed state."""

    default_code = codes.KORCH_RUN_FAILED


class RunTimeoutError(KorchError):
    """A run exceeded its ``max_supersteps`` or wall-clock bound."""

    default_code = codes.KORCH_RUN_TIMEOUT


class MissingExtraError(KorchError):
    """An optional extra is required but not installed.

    Raised at a lazy-import site instead of a bare ``ImportError``; the message names the extra
    and the exact ``pip install`` command.

    Example:
        >>> from korchestrator.exceptions import KorchError, MissingExtraError
        >>> try:
        ...     raise MissingExtraError(
        ...         "The cognitive layer requires the 'dspy' extra. "
        ...         "Install it with: pip install 'korchestrator[dspy]'"
        ...     )
        ... except KorchError as exc:
        ...     print(exc.code)
        KORCH_MISSING_EXTRA
    """

    default_code = codes.KORCH_MISSING_EXTRA


class ApiError(KorchError):
    """A :class:`~korchestrator.remote.KorchestratorClient` call failed (spec 04 §7.5).

    Raised for any non-2xx response the remote engine returns after retries are exhausted —
    ``status`` and ``trace_id`` let a caller correlate the failure with server-side logs and
    support without parsing the message text.

    Args:
        message: An actionable description of the failure.
        status: The HTTP status code the engine returned. Defaults to ``500`` so ``ApiError``
            stays constructible like every other ``KorchError`` when the status genuinely isn't
            known; real call sites always pass the response's actual status.
        code: The stable error code — the engine's own code when its response body carries one,
            else :attr:`default_code`.
        trace_id: The engine's request trace id, when the response provided one.

    Example:
        >>> from korchestrator.exceptions import ApiError, KorchError
        >>> err = ApiError("Run 'r1' not found.", status=404, trace_id="trace-abc")
        >>> err.status, err.trace_id, isinstance(err, KorchError)
        (404, 'trace-abc', True)
    """

    default_code = codes.KORCH_API_ERROR

    def __init__(
        self,
        message: str,
        *,
        status: int = 500,
        code: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Build the error with the engine's HTTP status and optional trace id."""
        super().__init__(message, code=code)
        self.status = status
        self.trace_id = trace_id
