"""Governance layer (L5).

Imports: korchestrator.governance.trust, stdlib, pydantic.

The policy engine: per-agent ``hitl_threshold`` with a ``GOVERNANCE_TRUST_THRESHOLD`` fallback,
deciding whether a superstep's trust score calls for a HITL intervention (spec 06 §7). Threshold
comparison only — the runtime pause signal itself is P7.4.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.governance.trust import GovernanceCheck

__all__ = ["GovernanceAction", "GovernanceDecision", "evaluate_policy"]


class GovernanceAction(str, Enum):
    """The policy engine's verdict: let the run continue, or call for a HITL intervention."""

    ALLOW = "allow"
    INTERVENE = "intervene"


class GovernanceDecision(BaseModel):
    """One agent's policy verdict for a superstep: the score, the threshold, and the action.

    Example:
        >>> from datetime import datetime, timezone
        >>> from korchestrator.governance import check_governance
        >>> from korchestrator.models.state import AgentState
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report",
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> check = check_governance(state)
        >>> decision = evaluate_policy(
        ...     check, agent_id="worker", hitl_threshold=None, global_threshold=0.5
        ... )
        >>> decision.action
        <GovernanceAction.ALLOW: 'allow'>
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    trust_score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    action: GovernanceAction
    reason: str


def evaluate_policy(
    check: GovernanceCheck,
    *,
    agent_id: str,
    hitl_threshold: float | None,
    global_threshold: float,
) -> GovernanceDecision:
    """Decide whether ``check``'s trust score calls for a HITL intervention.

    The effective threshold is ``hitl_threshold`` (an agent's own
    :attr:`~korchestrator.models.agent.AgentConfig.hitl_threshold`) when set, else
    ``global_threshold`` (the composition root's resolved ``GOVERNANCE_TRUST_THRESHOLD``, config/'s
    only reader — this function stays config-free and pure). Intervention triggers when
    ``trust_score`` is strictly below the threshold; this function only decides — the runtime pause
    signal that acts on an ``INTERVENE`` verdict is built in P7.4.

    Example:
        >>> from datetime import datetime, timezone
        >>> from korchestrator.governance import check_governance
        >>> from korchestrator.models.state import AgentState
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report", trust_score=0.3,
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> check = check_governance(state)
        >>> evaluate_policy(
        ...     check, agent_id="worker", hitl_threshold=None, global_threshold=0.5
        ... ).action
        <GovernanceAction.INTERVENE: 'intervene'>
    """
    threshold = hitl_threshold if hitl_threshold is not None else global_threshold
    action = GovernanceAction.INTERVENE if check.trust_score < threshold else GovernanceAction.ALLOW
    verb = "is below" if action is GovernanceAction.INTERVENE else "meets"
    reason = f"trust_score {check.trust_score:.2f} {verb} the {threshold:.2f} threshold"
    return GovernanceDecision(
        agent_id=agent_id,
        trust_score=check.trust_score,
        threshold=threshold,
        action=action,
        reason=reason,
    )
