"""Cognitive layer (L2). Imports: config, models, exceptions, stdlib, pydantic.

The built-in :class:`~korchestrator.models.routing.ModelCard` catalogue and the loader that
selects a card source from :class:`~korchestrator.config.Settings`. Cards are *data* — the cost,
latency, and quality figures an algorithmic or semantic router ranks over. The ``"url"`` source
needs an HTTP client (``httpx``, confined to ``clients``/``providers``) and is deferred; use
``"builtin"`` (default) or ``"file"``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError
from korchestrator.models.routing import ModelCard

__all__ = ["builtin_model_cards", "load_model_cards"]

# A small, representative catalogue with distinct cost/latency/quality so ranking is meaningful.
# Figures are illustrative defaults, not a live price sheet; override via a file source.
_BUILTIN: tuple[ModelCard, ...] = (
    ModelCard(
        name="gpt-4o",
        provider="openai",
        description="A high-quality general model for hard reasoning, planning, and synthesis.",
        capabilities=("reasoning", "planning", "summarization", "analysis", "code-generation"),
        context_window=128_000,
        cost_per_1k_input_usd=0.0025,
        cost_per_1k_output_usd=0.01,
        latency_p50_ms=900,
        quality_score=0.92,
        fallbacks=("gpt-4o-mini",),
    ),
    ModelCard(
        name="gpt-4o-mini",
        provider="openai",
        description="A small, fast, low-cost model for routine summarization and extraction.",
        capabilities=("summarization", "extraction", "general"),
        context_window=128_000,
        cost_per_1k_input_usd=0.00015,
        cost_per_1k_output_usd=0.0006,
        latency_p50_ms=400,
        quality_score=0.74,
    ),
    ModelCard(
        name="claude-3.5-sonnet",
        provider="anthropic",
        description="A strong general model balancing quality and speed for writing and analysis.",
        capabilities=("reasoning", "writing", "analysis", "code-generation"),
        context_window=200_000,
        cost_per_1k_input_usd=0.003,
        cost_per_1k_output_usd=0.015,
        latency_p50_ms=700,
        quality_score=0.90,
        fallbacks=("gpt-4o",),
    ),
    ModelCard(
        name="claude-3.5-haiku",
        provider="anthropic",
        description="A fast, economical model for high-volume routine tasks.",
        capabilities=("summarization", "extraction", "general"),
        context_window=200_000,
        cost_per_1k_input_usd=0.0008,
        cost_per_1k_output_usd=0.004,
        latency_p50_ms=350,
        quality_score=0.72,
    ),
)


def builtin_model_cards() -> tuple[ModelCard, ...]:
    """Return the built-in :class:`ModelCard` catalogue.

    Returns:
        The immutable built-in catalogue — the default candidate set for ranking strategies.

    Example:
        >>> from korchestrator.routing.model_cards import builtin_model_cards
        >>> "gpt-4o" in {card.name for card in builtin_model_cards()}
        True
    """
    return _BUILTIN


def load_model_cards(settings: Settings) -> tuple[ModelCard, ...]:
    """Load the candidate model cards named by ``settings.modelcard_source``.

    ``"builtin"`` (the default) returns the packaged catalogue offline. ``"file"`` reads a JSON
    array of card objects from ``settings.modelcard_path``. ``"url"`` is deferred (it needs an
    HTTP client outside this layer) and raises an actionable :class:`ConfigurationError`.

    Args:
        settings: The configuration selecting the source and its path.

    Returns:
        The loaded candidate cards.

    Raises:
        ConfigurationError: If the source is ``"file"`` without a path, the file is missing or
            malformed, or the source is ``"url"`` (deferred).

    Example:
        >>> from korchestrator.config import Settings
        >>> from korchestrator.routing.model_cards import load_model_cards
        >>> len(load_model_cards(Settings())) > 0  # builtin default
        True
    """
    source = settings.modelcard_source
    if source == "builtin":
        return _BUILTIN
    if source == "file":
        return _load_from_file(settings.modelcard_path)
    raise ConfigurationError(
        "MODELCARD_SOURCE='url' is not available in this release (it needs an HTTP client outside "
        "the routing layer). Use MODELCARD_SOURCE='builtin' or 'file' with MODELCARD_PATH."
    )


def _load_from_file(path: str | None) -> tuple[ModelCard, ...]:
    if not path:
        raise ConfigurationError(
            "MODELCARD_SOURCE='file' requires MODELCARD_PATH to point at a JSON array of model "
            "cards. Set MODELCARD_PATH, or use MODELCARD_SOURCE='builtin'."
        )
    file = Path(path)
    try:
        raw = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read the model-card file at {path!r}: {exc}. Check MODELCARD_PATH."
        ) from exc
    try:
        payload = json.loads(raw)
        return tuple(ModelCard.model_validate(entry) for entry in payload)
    except (json.JSONDecodeError, PydanticValidationError, TypeError) as exc:
        raise ConfigurationError(
            f"The model-card file at {path!r} must be a JSON array of model-card objects: {exc}."
        ) from exc
