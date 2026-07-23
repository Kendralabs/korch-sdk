"""Leaf-utility layer. Imports: stdlib (json, os, pathlib), pydantic, exceptions.

The single typed ``Settings`` object and the only place in the package that reads
environment variables or a ``.env`` file. Every other module receives configuration by
injection (spec 08 §1). ``Settings`` is built on ``pydantic.BaseModel`` rather than
``pydantic-settings`` so the base install stays ``pydantic``-only (ADR 0004, ADR 0009,
ADR 0016). Environment/``.env`` access is confined to :meth:`Settings.from_env`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from korchestrator.exceptions import ConfigurationError

__all__ = ["Settings"]

# Recognised scalar environment variables → Settings field names (pydantic coerces the raw
# string to the field type). This mapping plus the JSON and CSV maps below are the single
# authoritative list of what config/ reads from the environment (spec 08 §1.3).
_ENV_TO_FIELD: dict[str, str] = {
    "MOCK_LLM": "mock_llm",
    "KORCH_RUNTIME": "korch_runtime",
    "PERSISTENCE_BACKEND": "persistence_backend",
    # --- gateway (Phase 8) ---
    "KENDRA_AI_GATEWAY_URL": "kendra_ai_gateway_url",
    "KENDRA_GATEWAY_API_KEY": "kendra_gateway_api_key",
    # --- governance (Phase 7) ---
    "GOVERNANCE_TRUST_THRESHOLD": "governance_trust_threshold",
    # --- routing (Phase 5) ---
    "ROUTING_STRATEGY": "routing_strategy",
    "EMBEDDING_PROVIDER": "embedding_provider",
    "MODELCARD_SOURCE": "modelcard_source",
    "MODELCARD_PATH": "modelcard_path",
    "MODELCARD_URL": "modelcard_url",
    "MODELCARD_CACHE_TTL_SECONDS": "modelcard_cache_ttl_seconds",
    # --- kernel / runtime selection (Phase 8) ---
    "KORCH_MAX_SUPERSTEPS": "korch_max_supersteps",
    "KORCH_PLUGINS_ENABLED": "korch_plugins_enabled",
    # --- logging / telemetry (Phase 8) ---
    "KORCH_LOG_LEVEL": "korch_log_level",
    "KORCH_TELEMETRY_ENABLED": "korch_telemetry_enabled",
    # --- remote engine client (Phase 8/9) ---
    "KORCH_ENGINE_URL": "korch_engine_url",
    "KORCH_ENGINE_API_KEY": "korch_engine_api_key",
    "KORCH_ENGINE_NAMESPACE": "korch_engine_namespace",
    "KORCH_ENGINE_TASK_QUEUE": "korch_engine_task_queue",
    # --- Temporal runtime (Phase 8) ---
    "TEMPORAL_ADDRESS": "temporal_address",
    "TEMPORAL_NAMESPACE": "temporal_namespace",
    "TEMPORAL_TASK_QUEUE": "temporal_task_queue",
    "TEMPORAL_API_KEY": "temporal_api_key",
    "TEMPORAL_HITL_TIMEOUT_SECONDS": "temporal_hitl_timeout_seconds",
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

# LLM_GATEWAY_URL is a fallback *name* for KENDRA_AI_GATEWAY_URL, not a second field (spec 08
# §1.3: "alias fallback for the above") — used only when the primary name is absent.
_GATEWAY_URL_ALIAS = "LLM_GATEWAY_URL"


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


def _read_dotenv_file(path: str | Path) -> dict[str, str]:
    """Parse a ``.env`` file (``KEY=VALUE`` per line) into a raw string mapping.

    Blank lines and lines starting with ``#`` are ignored; a value's surrounding matched quotes
    (``"`` or ``'``) are stripped. Returns ``{}`` when the file does not exist — ``.env`` support
    is opt-in, never required. This is a deliberately minimal reader (ADR 0016): no interpolation,
    no export syntax, no multi-line values — the full ``pydantic-settings``/``python-dotenv``
    feature set this SDK does not currently need.
    """
    file = Path(path)
    if not file.is_file():
        return {}
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read the .env file at {file}: {exc}. Check its permissions, or pass "
            "dotenv_path=None to skip .env loading.",
            code="KORCH_CONFIG_INVALID",
        ) from exc
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        key = key.strip()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


class Settings(BaseModel):
    """Typed, injected configuration for the Korchestrator SDK.

    A plain, immutable configuration model. Bare construction performs no environment or file
    access — pass explicit values, or use :meth:`from_env` to layer ``.env``, the environment, and
    explicit overrides on top of the declared defaults. Every other module receives a ``Settings``
    instance by injection; nothing else reads the environment or a ``.env`` file.

    With no environment and no arguments, the defaults describe a zero-config local run: the
    offline MockLM gateway, the in-process ``local`` runtime, and in-memory persistence.

    Attributes:
        mock_llm: Use the deterministic offline MockLM gateway. Defaults to ``True``; under
            :meth:`from_env`, defaults to ``False`` when a gateway key is configured instead
            (spec 08 §1.3) — bare construction always defaults to ``True``.
        korch_runtime: Which durable runtime drives the superstep loop — ``"local"``
            in-process, or ``"temporal"`` for durable execution.
        persistence_backend: Which context-graph backend to use; ``"none"`` runs fully
            standalone with no external store.
        kendra_ai_gateway_url: The model gateway's base URL. ``LLM_GATEWAY_URL`` is a
            recognised alias environment variable name for this same field.
        kendra_gateway_api_key: The model gateway's API key. Never logged or serialised in
            plain text (``SecretStr``).
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
        korch_max_supersteps: The default hard halt bound for a run (1-100).
        korch_plugins_enabled: Whether entry-point plugin discovery (connectors, routers) runs.
        korch_log_level: The level :func:`~korchestrator.logging.enable_logging` defaults to.
        korch_telemetry_enabled: Whether OTel instrumentation is active (``[otel]`` extra).
        korch_engine_url: The remote Korchestrator engine's base URL (``[remote]`` extra).
        korch_engine_api_key: The remote engine's API key (``SecretStr``).
        korch_engine_namespace: The remote engine's namespace.
        korch_engine_task_queue: The remote engine's task queue name.
        temporal_address: The Temporal server address for the durable runtime.
        temporal_namespace: The Temporal namespace.
        temporal_task_queue: The Temporal task queue name.
        temporal_api_key: The Temporal Cloud API key; when set, the connection uses TLS
            (``SecretStr``).
        temporal_hitl_timeout_seconds: How long a ``governance_paused`` run waits for a signal
            before transitioning to ``timed_out`` (spec 06 §7).

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

    # --- gateway (Phase 8) ---
    kendra_ai_gateway_url: str | None = None
    kendra_gateway_api_key: SecretStr | None = None

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

    # --- kernel / runtime selection (Phase 8) ---
    korch_max_supersteps: int = Field(default=10, ge=1, le=100)
    korch_plugins_enabled: bool = False

    # --- logging / telemetry (Phase 8) ---
    korch_log_level: str = "WARNING"
    korch_telemetry_enabled: bool = False

    # --- remote engine client (Phase 8/9) ---
    korch_engine_url: str | None = None
    korch_engine_api_key: SecretStr | None = None
    korch_engine_namespace: str = "default"
    korch_engine_task_queue: str = "korchestrator"

    # --- Temporal runtime (Phase 8) ---
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "korchestrator"
    temporal_api_key: SecretStr | None = None
    temporal_hitl_timeout_seconds: int = Field(default=86400, gt=0)

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | Path | None = None,
        # `Any`: overrides are heterogeneous field values (bool, Literal strings) validated by
        # pydantic on construction; a precise union would just restate the field types.
        **overrides: Any,
    ) -> Settings:
        """Build ``Settings`` from the environment (and optionally ``.env``) plus overrides.

        Precedence, highest first: keyword argument, environment variable, ``.env`` file entry
        (only when ``dotenv_path`` is given), declared default. Only the recognised variables (the
        scalar, JSON, and CSV maps at module top) are read; any other variable is ignored. Scalar
        values are validated by pydantic, so an unrecognised runtime, backend, or strategy raises a
        ``pydantic.ValidationError`` at construction rather than at first use; malformed JSON
        raises an actionable :class:`~korchestrator.exceptions.ConfigurationError`.

        ``.env`` loading is **opt-in** here (``dotenv_path`` defaults to ``None``) so this method
        stays side-effect-free by default for internal callers (``Korch``/``Swarm`` resolve
        settings via a bare ``from_env()`` call per run) and for tests. :func:`~korchestrator.
        config.configure` — the process-wide, application-startup entry point — passes
        ``dotenv_path=".env"`` by default, matching spec 08 §1's precedence chain for the caller
        that is actually expected to load a project's ``.env`` file.

        ``mock_llm``, when not explicitly set by an override, ``.env``, or the environment,
        defaults to ``False`` if a gateway key (``KENDRA_GATEWAY_API_KEY``) resolved, else ``True``
        (spec 08 §1.3) — bare ``Settings()`` construction is unaffected and always defaults to
        ``True``.

        Args:
            dotenv_path: Path to a ``.env`` file to layer in. ``None`` (the default) skips
                ``.env`` entirely; a missing file at the given path is not an error.
            **overrides: Explicit field values that take precedence over everything else.

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
        dotenv_values = _read_dotenv_file(dotenv_path) if dotenv_path is not None else {}
        raw: dict[str, str] = {**dotenv_values, **os.environ}

        env: dict[str, Any] = {
            field: raw[var] for var, field in _ENV_TO_FIELD.items() if var in raw
        }
        if "kendra_ai_gateway_url" not in env and _GATEWAY_URL_ALIAS in raw:
            env["kendra_ai_gateway_url"] = raw[_GATEWAY_URL_ALIAS]
        for var, field in _ENV_JSON_TO_FIELD.items():
            if var in raw:
                env[field] = _parse_json_env(var, raw[var])
        for var, field in _ENV_CSV_TO_FIELD.items():
            if var in raw:
                env[field] = tuple(part.strip() for part in raw[var].split(",") if part.strip())

        merged = {**env, **overrides}
        if "mock_llm" not in merged:
            merged["mock_llm"] = merged.get("kendra_gateway_api_key") is None
        return cls(**merged)
