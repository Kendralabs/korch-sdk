"""Contract layer. Imports: korchestrator.models.state, stdlib, pydantic.

The remote engine's run-outcome shapes (spec 04 §7.3/§7.4) — what
:class:`~korchestrator.clients.KorchestratorClient`'s run-lifecycle methods return. Deliberately
distinct from the local kernel's :class:`~korchestrator.models.result.RunResult`: spec 04 §7
pins the documented *concepts* (§7.1) and the lifecycle/status vocabulary (§7.4), not a full wire
schema, and the engine's response never carries the kernel's internal nested ``AgentState``
snapshot — reusing ``RunResult`` verbatim would mean fabricating fields the engine never sends.
Frozen and ``extra="forbid"``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.models.state import RunStatus

__all__ = ["RemoteRunResult", "RunSummary"]


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
