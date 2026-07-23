"""Contract layer. Imports: korchestrator.models.state, stdlib, pydantic.

The remote engine's wire-facing shapes (spec 04 §7.3/§7.4) — what
:class:`~korchestrator.clients.KorchestratorClient`'s methods return: run outcomes
(``RemoteRunResult``/``RunSummary``), caller identity and usage (``CallerIdentity``/``Quota``),
and API key management (``ApiKey``/``ApiKeySummary``). Deliberately distinct from the local
kernel's :class:`~korchestrator.models.result.RunResult`: spec 04 §7 pins the documented
*concepts* (§7.1) and the lifecycle/status vocabulary (§7.4), not a full wire schema, and the
engine's response never carries the kernel's internal nested ``AgentState`` snapshot — reusing
``RunResult`` verbatim would mean fabricating fields the engine never sends. Frozen and
``extra="forbid"``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from korchestrator.models.state import RunStatus
from korchestrator.types import JSONValue

__all__ = [
    "ApiKey",
    "ApiKeySummary",
    "CallerIdentity",
    "Quota",
    "RemoteRunResult",
    "RunEvent",
    "RunSummary",
]


class RemoteRunResult(BaseModel):
    """A run's outcome as the remote engine reports it — terminal, paused, or still running.

    Returned by :meth:`KorchestratorClient.run`, ``run_swarm``, ``get_run``, ``wait``, and
    ``run_and_wait`` (spec 04 §7.3's ``POST /v1/run/auto``, ``POST /v1/run/swarm``,
    ``GET /v1/run/{id}``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    status: RunStatus
    final_answer: str = ""
    supersteps: int = Field(default=0, ge=0)
    trust_score: float = Field(default=1.0, ge=0.0, le=1.0)
    message_count: int = Field(default=0, ge=0)
    error_code: str | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class RunEvent(BaseModel):
    """One live event from a run's SSE stream (``GET /v1/run/{id}/stream``, spec 04 §7.3/§7.5).

    Deliberately mirrors :class:`korchestrator.events.Event`'s shape (``name``/``payload``/
    ``run_id``) — the same concept, one streamed event — without importing across the
    ``clients``/``events`` module boundary spec 05's allowed-imports table doesn't authorize
    (``clients/`` reuses the same purpose-built-model pattern this file already uses for
    :class:`RemoteRunResult` rather than the local kernel's ``RunResult``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    name: str
    payload: Mapping[str, JSONValue] = Field(default_factory=dict)


class RunSummary(BaseModel):
    """A lightweight run summary — ``GET /v1/runs/{id}/summary`` and the terminal-state webhook.

    Returned by :meth:`KorchestratorClient.get_run_summary` and, as a tuple, ``list_runs``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    status: RunStatus
    superstep: int = Field(default=0, ge=0)
    final_answer: str = ""
    message_count: int = Field(default=0, ge=0)
    completed_at: datetime | None = None


class CallerIdentity(BaseModel):
    """The authenticated caller's identity (``GET /v1/me``, spec 04 §7.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    scopes: tuple[str, ...] = ()


class Quota(BaseModel):
    """The caller's usage quota (``GET /v1/me/quota``, spec 04 §7.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limit: int = Field(ge=0)
    used: int = Field(ge=0)
    remaining: int = Field(ge=0)
    resets_at: datetime | None = None


class ApiKey(BaseModel):
    """A newly created API key (``POST /v1/keys``, spec 04 §7.3).

    The secret is returned once, at creation — the engine never returns it again, matching every
    common API-key UX. ``key`` is a :class:`~pydantic.SecretStr` so an accidental ``repr``/``str``
    (a log line, a stray ``print``) never leaks it; call ``key.get_secret_value()`` to use it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    key: SecretStr
    scopes: tuple[str, ...] = ()
    created_at: datetime


class ApiKeySummary(BaseModel):
    """An existing API key's metadata (``GET /v1/keys``, spec 04 §7.3) — never the secret."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    scopes: tuple[str, ...] = ()
    created_at: datetime
