"""Leaf-utility layer.

Imports: korchestrator.exceptions, stdlib (logging).

The single namespaced ``korchestrator`` logger. A ``NullHandler`` is attached the moment this
module is imported, so the SDK is silent by default (spec 08 §3) — no "no handlers could be
found" warning and no unsolicited output on an embedding application's console.
``enable_logging``/``disable_logging`` are the only supported way the SDK ever writes logs; the
root logger and ``logging.basicConfig()`` are never touched.
"""

from __future__ import annotations

import logging
from typing import TextIO

from korchestrator.exceptions import ValidationError

__all__ = ["disable_logging", "enable_logging"]

_LOGGER_NAME = "korchestrator"
_VALID_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"})

_logger = logging.getLogger(_LOGGER_NAME)
_logger.addHandler(logging.NullHandler())

_handler: logging.Handler | None = None


def enable_logging(level: str = "INFO", *, stream: TextIO | None = None) -> None:
    """Attach a single ``StreamHandler`` to the ``korchestrator`` logger (spec 08 §3).

    Idempotent — calling this again replaces the previously attached handler and level rather
    than stacking a second one. Never touches the root logger and never calls
    ``logging.basicConfig()``, so an embedding application's own logging configuration stays
    untouched.

    Args:
        level: The log level name, case-insensitive (``"DEBUG"``, ``"INFO"``, ``"WARNING"``,
            ``"ERROR"``, ``"CRITICAL"``, or ``"NOTSET"``). Defaults to ``"INFO"``.
        stream: Where to write; defaults to ``sys.stderr`` (``logging.StreamHandler``'s own
            default when ``stream`` is ``None``).

    Raises:
        ValidationError: If ``level`` is not a recognised level name.

    Example:
        >>> from korchestrator.logging import disable_logging, enable_logging
        >>> enable_logging("DEBUG")
        >>> disable_logging()
    """
    global _handler
    normalized = level.upper()
    if normalized not in _VALID_LEVELS:
        raise ValidationError(
            f"Unrecognised log level {level!r}. Valid levels: {', '.join(sorted(_VALID_LEVELS))}.",
            code="KORCH_VALIDATION_FAILED",
        )
    if _handler is not None:
        _logger.removeHandler(_handler)
    _handler = logging.StreamHandler(stream)
    _logger.addHandler(_handler)
    _logger.setLevel(normalized)


def disable_logging() -> None:
    """Remove the handler :func:`enable_logging` attached, if any. Idempotent.

    Example:
        >>> from korchestrator.logging import disable_logging, enable_logging
        >>> enable_logging()
        >>> disable_logging()
        >>> disable_logging()  # idempotent -- a second call is a no-op
    """
    global _handler
    if _handler is not None:
        _logger.removeHandler(_handler)
        _handler = None
