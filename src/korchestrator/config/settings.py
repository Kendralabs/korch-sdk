"""Leaf-utility layer. Imports: stdlib (os), pydantic.

The single typed ``Settings`` object and the only place in the package that reads
environment variables. Every other module receives configuration by injection
(spec 08 §1). During Phase 0 it carries only the fields Phases 0-3 need; Phase 8
finalizes the full variable table, ``.env`` loading, ``configure()`` and
``get_settings()``.

``Settings`` is built on ``pydantic.BaseModel`` rather than ``pydantic-settings`` so the
base install stays ``pydantic``-only (ADR 0004, ADR 0009). Environment access is confined
to :meth:`Settings.from_env`.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

__all__ = ["Settings"]

# Recognised environment variables → Settings field names. This mapping is the single
# authoritative list of what config/ reads from the environment during Phases 0-3.
_ENV_TO_FIELD: dict[str, str] = {
    "MOCK_LLM": "mock_llm",
    "KORCH_RUNTIME": "korch_runtime",
    "PERSISTENCE_BACKEND": "persistence_backend",
}


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

    Example:
        >>> from korchestrator.config import Settings
        >>> Settings().korch_runtime
        'local'
        >>> Settings(korch_runtime="temporal").korch_runtime
        'temporal'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mock_llm: bool = True
    korch_runtime: Literal["local", "temporal"] = "local"
    persistence_backend: Literal["none", "memory", "kcg"] = "memory"

    @classmethod
    def from_env(
        cls,
        # `Any`: overrides are heterogeneous field values (bool, Literal strings) validated by
        # pydantic on construction; a precise union would just restate the field types.
        **overrides: Any,
    ) -> Settings:
        """Build ``Settings`` from the environment, with explicit overrides winning.

        Precedence, highest first: keyword argument, environment variable, declared
        default. Only the recognised variables (``MOCK_LLM``, ``KORCH_RUNTIME``,
        ``PERSISTENCE_BACKEND``) are read; any other variable is ignored. Values are
        validated by pydantic, so an unrecognised runtime or backend raises a
        ``pydantic.ValidationError`` at construction rather than at first use.

        Args:
            **overrides: Explicit field values that take precedence over the environment.

        Returns:
            A validated, immutable :class:`Settings`.

        Example:
            >>> from korchestrator.config import Settings
            >>> Settings().persistence_backend  # bare construction reads no environment
            'memory'
            >>> Settings.from_env(korch_runtime="temporal").korch_runtime  # explicit arg wins
            'temporal'
        """
        from_environment = {
            field: os.environ[var] for var, field in _ENV_TO_FIELD.items() if var in os.environ
        }
        return cls(**{**from_environment, **overrides})
