"""Leaf-utility layer. Imports: stdlib (os, json), pydantic, exceptions.

The single typed ``Settings`` object and the only place in the package that reads
environment variables. Every other module receives configuration by injection
(spec 08 §1). It grows a variable group per phase (Phases 0-3 core, Phase 5 routing);
Phase 8 finalizes the full variable table, ``.env`` loading, ``configure()`` and
``get_settings()``.

``Settings`` is built on ``pydantic.BaseModel`` rather than ``pydantic-settings`` so the
base install stays ``pydantic``-only (ADR 0004, ADR 0009). Environment access is confined
to :meth:`Settings.from_env`.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.exceptions import ConfigurationError

__all__ = ["Settings"]

# Recognised scalar environment variables → Settings field names (pydantic coerces the raw
# string to the field type). This mapping plus the JSON and CSV maps below are the single
# authoritative list of what config/ reads from the environment.
_ENV_TO_FIELD: dict[str, str] = {
    "MOCK_LLM": "mock_llm",
    "KORCH_RUNTIME": "korch_runtime",
    "PERSISTENCE_BACKEND": "persistence_backend",
    # --- governance (Phase 7) ---
    "GOVERNANCE_TRUST_THRESHOLD": "governance_trust_threshold",
    # --- routing (Phase 5) ---
    "ROUTING_STRATEGY": "routing_strategy",
    "EMBEDDING_PROVIDER": "embedding_provider",
    "MODELCARD_SOURCE": "modelcard_source",
    "MODELCARD_PATH": "modelcard_path",
    "MODELCARD_URL": "modelcard_url",
    "MODELCARD_CACHE_TTL_SECONDS": "modelcard_cache_ttl_seconds",
}

# JSON-object environment variables → field names (parsed with ``json.loads``).
_ENV_JSON_TO_FIELD: dict[str, str] = {
    "AGENT_MODEL_MAP": "agent_model_map",
    "ROUTING_WEIGHTS": "routing_weights",
}

# Comma-separated environment variables → tuple field names.
_ENV_CSV_TO_FIELD: dict[str, str] = {
    "ROUTING_PRIORITY_ORDER": "routing_priority_order",
}


def _default_routing_weights() -> dict[str, float]:
    """The default algorithmic weights (spec 08 §1) — quality-led, then cost, then latency."""
    return {"quality": 0.5, "cost": 0.3, "latency": 0.2}


def _parse_json_env(var: str, raw: str) -> Any:
    """Parse a JSON environment value, raising an actionable ``ConfigurationError`` on garbage."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"Environment variable {var} must be valid JSON, got {raw!r}. "
            f'For {var}, use e.g. \'{{"lead": "gpt-4o"}}\'.'
        ) from exc


class Settings(BaseModel):
    """Typed, injected configuration for the Korchestrator SDK.

    A plain, immutable configuration model. Bare construction performs no environment
    access — pass explicit values, or use :meth:`from_env` to layer the environment on top
    of the declared defaults. Every other module receives a ``Settings`` instance by
    injection; nothing else reads the environment.

    With no environment and no arguments, the defaults describe a zero-config local run:
    the offline MockLM gateway, the in-process ``local`` runtime, and in-memory persistence.

    Attributes:
        mock_llm: Use the deterministic offline MockLM gateway. Defaults to ``True`` so a
            fresh install runs with no network and no API key. (The conditional "off when a
            gateway key is present" default arrives with the gateway fields in Phase 8.)
        korch_runtime: Which durable runtime drives the superstep loop — ``"local"``
            in-process, or ``"temporal"`` for durable execution.
        persistence_backend: Which context-graph backend to use; ``"none"`` runs fully
            standalone with no external store.
        governance_trust_threshold: The global fallback HITL intervention threshold
            (``GOVERNANCE_TRUST_THRESHOLD``, spec 08 §1.3), used when an agent has no
            per-agent ``AgentConfig.hitl_threshold`` of its own.
        routing_strategy: How a model is chosen per agent — ``"explicit"`` (the default; works
            with no extra) plus its fallback, ``"algorithmic"``, ``"semantic"`` (needs the
            ``[routing]`` extra), or ``"composite"``.
        agent_model_map: Explicit ``agent_id → model`` overrides for the explicit strategy.
        routing_weights: Algorithmic ranking weights over ``"quality"``, ``"cost"``, ``"latency"``.
        routing_priority_order: The composite fallback chain, tried in order; ``"fallback"`` is the
            always-succeeds tail that keeps the default install resolvable.
        embedding_provider: The embedding backend name for the semantic strategy (``[routing]``).
        modelcard_source: Where candidate :class:`ModelCard`s come from — ``"builtin"`` (default),
            ``"file"``, or ``"url"``.
        modelcard_path: Path to a JSON model-card file when ``modelcard_source="file"``.
        modelcard_url: URL of a model-card document when ``modelcard_source="url"``.
        modelcard_cache_ttl_seconds: How long the semantic strategy caches card embeddings.

    Example:
        >>> from korchestrator.config import Settings
        >>> Settings().korch_runtime
        'local'
        >>> Settings(korch_runtime="temporal").korch_runtime
        'temporal'
        >>> Settings().routing_strategy
        'explicit'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mock_llm: bool = True
    korch_runtime: Literal["local", "temporal"] = "local"
    persistence_backend: Literal["none", "memory", "kcg"] = "memory"

    # --- governance (Phase 7) ---
    governance_trust_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # --- routing (Phase 5) ---
    routing_strategy: Literal["explicit", "semantic", "algorithmic", "composite"] = "explicit"
    agent_model_map: dict[str, str] = Field(default_factory=dict)
    routing_weights: dict[str, float] = Field(default_factory=_default_routing_weights)
    routing_priority_order: tuple[str, ...] = ("explicit", "algorithmic", "fallback")
    embedding_provider: str | None = None
    modelcard_source: Literal["builtin", "file", "url"] = "builtin"
    modelcard_path: str | None = None
    modelcard_url: str | None = None
    modelcard_cache_ttl_seconds: int = Field(default=900, ge=0)

    @classmethod
    def from_env(
        cls,
        # `Any`: overrides are heterogeneous field values (bool, Literal strings) validated by
        # pydantic on construction; a precise union would just restate the field types.
        **overrides: Any,
    ) -> Settings:
        """Build ``Settings`` from the environment, with explicit overrides winning.

        Precedence, highest first: keyword argument, environment variable, declared
        default. Only the recognised variables (the scalar, JSON, and CSV maps at module
        top) are read; any other variable is ignored. Scalar values are validated by
        pydantic, so an unrecognised runtime, backend, or strategy raises a
        ``pydantic.ValidationError`` at construction rather than at first use; malformed
        JSON raises an actionable :class:`ConfigurationError`.

        Args:
            **overrides: Explicit field values that take precedence over the environment.

        Returns:
            A validated, immutable :class:`Settings`.

        Raises:
            ConfigurationError: If a JSON-typed variable (``AGENT_MODEL_MAP``,
                ``ROUTING_WEIGHTS``) holds invalid JSON.

        Example:
            >>> from korchestrator.config import Settings
            >>> Settings().persistence_backend  # bare construction reads no environment
            'memory'
            >>> Settings.from_env(korch_runtime="temporal").korch_runtime  # explicit arg wins
            'temporal'
        """
        env: dict[str, Any] = {
            field: os.environ[var] for var, field in _ENV_TO_FIELD.items() if var in os.environ
        }
        for var, field in _ENV_JSON_TO_FIELD.items():
            if var in os.environ:
                env[field] = _parse_json_env(var, os.environ[var])
        for var, field in _ENV_CSV_TO_FIELD.items():
            if var in os.environ:
                env[field] = tuple(
                    part.strip() for part in os.environ[var].split(",") if part.strip()
                )
        return cls(**{**env, **overrides})
