"""Governance layer (L5). Imports: korchestrator.types, stdlib, pydantic.

The governance-facing telemetry snapshot fed by each completed superstep.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ControlTowerTelemetry"]


class ControlTowerTelemetry(BaseModel):
    """One superstep's governance-relevant snapshot.

    Named for the platform's Control Tower telemetry feed (the governance-facing read of a
    superstep). It is derived read-only from the terminal :class:`~korchestrator.models.state.
    AgentState` by :func:`korchestrator.governance.trust.derive_telemetry` — never a second source
    of truth for ``trust_score``, which the kernel's barrier computes (spec 06 §3, P7.2).

    Attributes:
        run_id: The run this telemetry belongs to.
        tenant_id: The tenant the run executed under.
        superstep: The (0-based) superstep this snapshot describes.
        trust_score: The trust score as of this superstep, 0.0-1.0.
        active_agent_ids: Agents that emitted a message during this superstep, sorted. An agent
            that only wrote a context channel (no message) does not appear — a known limitation
            of deriving telemetry from ``AgentState`` alone rather than the raw per-superstep
            ``StateUpdate`` records, which are not retained once the barrier applies them.
        valid_time: The barrier's stamped transaction time for this superstep (replay-safe).

    Example:
        >>> from datetime import datetime, timezone
        >>> ControlTowerTelemetry(
        ...     run_id="r1", tenant_id="default", superstep=0, trust_score=0.9,
        ...     active_agent_ids=("worker",), valid_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... ).trust_score
        0.9
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    tenant_id: str
    superstep: int = Field(ge=0)
    trust_score: float = Field(ge=0.0, le=1.0)
    active_agent_ids: tuple[str, ...] = ()
    valid_time: datetime
