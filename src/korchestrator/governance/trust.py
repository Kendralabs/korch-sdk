"""Governance layer (L5).

Imports: korchestrator.models, korchestrator.governance.telemetry, stdlib, pydantic.

Trust scoring's governance-facing read: :func:`check_governance` observes the trust score the
kernel already computed and packages this superstep's :class:`~korchestrator.governance.
telemetry.ControlTowerTelemetry`. Threshold comparison, ``hitl_threshold``/
``GOVERNANCE_TRUST_THRESHOLD`` fallback, and the policy engine land in P7.3; the runtime pause
signal lands in P7.4. This module only observes — it never mutates state and never recomputes
``trust_score`` (spec 05 §3.1, spec 06 §7, spec 11/12 P7.2).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.governance.telemetry import ControlTowerTelemetry
from korchestrator.models.state import AgentState

__all__ = ["GovernanceCheck", "check_governance", "derive_telemetry"]


class GovernanceCheck(BaseModel):
    """The governance-facing view of a run after a superstep: its score, plus the telemetry.

    Example:
        >>> from datetime import datetime, timezone
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report",
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> check_governance(state).trust_score
        1.0
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    trust_score: float = Field(ge=0.0, le=1.0)
    telemetry: ControlTowerTelemetry


def derive_telemetry(state: AgentState) -> ControlTowerTelemetry:
    """Derive this superstep's :class:`ControlTowerTelemetry` from a completed ``AgentState``.

    Pure and read-only. ``state.superstep`` has already advanced past the superstep the barrier
    just computed (spec 06 §2), so the telemetry describes ``state.superstep - 1`` (floored at 0
    for the initial, not-yet-run state) — the agents that emitted a message in that superstep, and
    the trust score as of it.

    Example:
        >>> from datetime import datetime, timezone
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report",
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> derive_telemetry(state).active_agent_ids
        ()
    """
    superstep = max(state.superstep - 1, 0)
    active_agent_ids = tuple(
        sorted({message.sender for message in state.messages if message.superstep == superstep})
    )
    return ControlTowerTelemetry(
        run_id=state.run_id,
        tenant_id=state.tenant_id,
        superstep=superstep,
        trust_score=state.trust_score,
        active_agent_ids=active_agent_ids,
        valid_time=state.transaction_time,
    )


def check_governance(state: AgentState) -> GovernanceCheck:
    """Read the kernel-computed trust score and this superstep's telemetry.

    ``trust_score`` is the kernel's: the barrier folds each active agent's ``StateUpdate.
    trust_delta`` into it every superstep, clamped to ``[0.0, 1.0]`` (``core.pregel``). This
    function is governance's read of that score plus the :class:`ControlTowerTelemetry` snapshot
    that P7.3's policy engine and audit log will consume — it does not itself decide whether to
    intervene.

    Example:
        >>> from datetime import datetime, timezone
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report",
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> result = check_governance(state)
        >>> (result.trust_score, result.telemetry.superstep)
        (1.0, 0)
    """
    return GovernanceCheck(trust_score=state.trust_score, telemetry=derive_telemetry(state))
