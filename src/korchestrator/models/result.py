"""Contract layer. Imports: korchestrator.models.state, stdlib, pydantic.

The terminal (or paused) ``RunResult`` returned by every public entry point, identical across
runtimes. ``final_answer`` is derived (the concatenation of every ``kind == "answer"`` message's
content, in order), never independently authored. Frozen and ``extra="forbid"``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.models.state import AgentState, Message, RunStatus

__all__ = ["RunResult"]


class RunResult(BaseModel):
    """Terminal (or paused) outcome of a run, identical across runtimes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run_id: str
    status: RunStatus
    final_answer: str
    supersteps: int = Field(ge=0)
    messages: tuple[Message, ...] = ()
    state: AgentState
    trust_score: float = Field(ge=0.0, le=1.0)
    error_code: str | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
