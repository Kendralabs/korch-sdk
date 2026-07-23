"""Leaf-utility layer.

Imports: korchestrator.config.settings, korchestrator.exceptions, pydantic, stdlib.

The process-wide installed :class:`~korchestrator.config.settings.Settings` instance:
:func:`configure` validates and installs a new one; :func:`get_settings` returns the current one,
building the zero-config default lazily on first call. No import-time singleton (B8) — the
instance is created only when one of these two functions is first called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from korchestrator.config.settings import Settings
from korchestrator.exceptions import ValidationError

__all__ = ["configure", "get_settings"]

_installed: Settings | None = None


def configure(*, dotenv_path: str | Path | None = ".env", **overrides: Any) -> Settings:
    """Build, validate, and install a new process-wide :class:`Settings` (spec 08 §1.2).

    Layers ``overrides`` over the environment, an optional ``.env`` file, and the declared
    defaults (:meth:`Settings.from_env`'s precedence), validates the result immediately, and
    installs it as what :func:`get_settings` subsequently returns. Unlike a bare
    ``Settings.from_env()`` call, ``configure()`` reads ``.env`` from the current working directory
    by default — this is the application-startup entry point spec 08 §1's precedence chain has in
    mind; pass ``dotenv_path=None`` to skip it.

    MUST NOT be called from inside a superstep — it mutates process-wide state, which would be a
    determinism violation in workflow scope (spec 06 §5). Tests use a ``settings`` fixture that
    resets the installed instance on teardown so no test leaks state into another.

    Args:
        dotenv_path: Path to a ``.env`` file to layer in; ``None`` skips it. Defaults to ``.env``
            in the current working directory; a missing file is not an error.
        **overrides: Explicit field values; see :class:`Settings` for the full list.

    Returns:
        The newly installed, validated :class:`Settings`.

    Raises:
        ValidationError: If an override or a resolved environment value fails structural
            validation (wraps the underlying ``pydantic.ValidationError``; spec 08 §1.2).

    Example:
        >>> from korchestrator.config import configure, get_settings
        >>> _ = configure(dotenv_path=None, korch_runtime="local", governance_trust_threshold=0.7)
        >>> get_settings().governance_trust_threshold
        0.7
    """
    global _installed
    try:
        settings = Settings.from_env(dotenv_path=dotenv_path, **overrides)
    except PydanticValidationError as exc:
        raise ValidationError(
            f"Invalid configuration: {exc}. Check the values passed to configure().",
            code="KORCH_VALIDATION_FAILED",
        ) from exc
    _installed = settings
    return settings


def get_settings() -> Settings:
    """Return the installed :class:`Settings`, building the zero-config default on first call.

    The result is cached; :func:`configure` is the only way to replace it.

    Example:
        >>> from korchestrator.config import configure, get_settings
        >>> _ = configure(dotenv_path=None, korch_runtime="local")
        >>> get_settings().korch_runtime
        'local'
    """
    global _installed
    if _installed is None:
        _installed = Settings.from_env()
    return _installed
