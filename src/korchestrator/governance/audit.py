"""Governance layer (L5).

Imports: korchestrator.governance.{policy,telemetry}, stdlib, pydantic.

The audit log: an append-only, in-memory record of governance decisions and the telemetry each was
based on.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from korchestrator.governance.policy import GovernanceDecision
from korchestrator.governance.telemetry import ControlTowerTelemetry

__all__ = ["AuditEntry", "AuditLog"]


class AuditEntry(BaseModel):
    """One immutable audit record: a governance decision plus the telemetry it was based on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    telemetry: ControlTowerTelemetry
    decision: GovernanceDecision
    recorded_at: datetime


class AuditLog:
    """An append-only, in-memory audit trail of governance decisions.

    Not durable across process restarts — the standalone default that works even under
    ``PERSISTENCE_BACKEND=none``. A composition root that wires a persistent
    :class:`~korchestrator.persistence.ContextGraphClient` (P7.6) additionally forwards entries
    there for the bitemporal, queryable trail; this log never reads the wall clock itself —
    ``recorded_at`` is always supplied by the caller, so it stays replay-safe wherever it is used.

    Example:
        >>> from datetime import datetime, timezone
        >>> from korchestrator.governance import check_governance, evaluate_policy
        >>> from korchestrator.models.state import AgentState
        >>> now = datetime(2026, 7, 23, tzinfo=timezone.utc)
        >>> state = AgentState(run_id="r1", objective="summarize the quarterly report",
        ...                     transaction_time=now)
        >>> check = check_governance(state)
        >>> decision = evaluate_policy(
        ...     check, agent_id="worker", hitl_threshold=None, global_threshold=0.5
        ... )
        >>> log = AuditLog()
        >>> _ = log.record(check.telemetry, decision, recorded_at=now)
        >>> len(log.entries)
        1
    """

    def __init__(self) -> None:
        """Start with an empty, in-memory audit trail."""
        self._entries: list[AuditEntry] = []

    def record(
        self,
        telemetry: ControlTowerTelemetry,
        decision: GovernanceDecision,
        *,
        recorded_at: datetime,
    ) -> AuditEntry:
        """Append and return a new immutable :class:`AuditEntry`."""
        entry = AuditEntry(telemetry=telemetry, decision=decision, recorded_at=recorded_at)
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        """Return every recorded entry, oldest first."""
        return tuple(self._entries)

    def for_run(self, run_id: str) -> tuple[AuditEntry, ...]:
        """Return the entries whose telemetry belongs to ``run_id``, oldest first."""
        return tuple(entry for entry in self._entries if entry.telemetry.run_id == run_id)
