"""Unit tests for the governance policy engine (spec 06 §7, P7.3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from korchestrator.governance import GovernanceAction, check_governance, evaluate_policy
from korchestrator.governance.trust import GovernanceCheck
from korchestrator.models.state import AgentState

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _check(trust_score: float) -> GovernanceCheck:
    state = AgentState(
        run_id="r1",
        objective="summarize the quarterly report",
        trust_score=trust_score,
        transaction_time=NOW,
    )
    return check_governance(state)


def test_a_score_at_or_above_the_threshold_is_allowed() -> None:
    decision = evaluate_policy(
        _check(0.5), agent_id="worker", hitl_threshold=None, global_threshold=0.5
    )
    assert decision.action is GovernanceAction.ALLOW
    assert decision.threshold == 0.5


def test_a_score_below_the_threshold_intervenes() -> None:
    decision = evaluate_policy(
        _check(0.4), agent_id="worker", hitl_threshold=None, global_threshold=0.5
    )
    assert decision.action is GovernanceAction.INTERVENE
    assert "below" in decision.reason


def test_a_per_agent_hitl_threshold_overrides_the_global_fallback() -> None:
    # The global fallback would allow 0.6, but this agent's own (stricter) threshold intervenes.
    decision = evaluate_policy(
        _check(0.6), agent_id="worker", hitl_threshold=0.8, global_threshold=0.5
    )
    assert decision.action is GovernanceAction.INTERVENE
    assert decision.threshold == 0.8


def test_a_lenient_per_agent_threshold_can_allow_what_the_global_would_block() -> None:
    decision = evaluate_policy(
        _check(0.3), agent_id="worker", hitl_threshold=0.2, global_threshold=0.5
    )
    assert decision.action is GovernanceAction.ALLOW
    assert decision.threshold == 0.2


@pytest.mark.parametrize("trust_score", [0.0, 0.1, 0.49, 0.5, 0.51, 1.0])
def test_the_decision_carries_the_scores_trust_score(trust_score: float) -> None:
    decision = evaluate_policy(
        _check(trust_score), agent_id="worker", hitl_threshold=None, global_threshold=0.5
    )
    assert decision.trust_score == trust_score


def test_the_decision_names_the_agent() -> None:
    decision = evaluate_policy(
        _check(1.0), agent_id="reviewer", hitl_threshold=None, global_threshold=0.5
    )
    assert decision.agent_id == "reviewer"
