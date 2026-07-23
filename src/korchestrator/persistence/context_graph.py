"""Context layer (L3).

Imports: korchestrator.interfaces, korchestrator.models, korchestrator.security, stdlib.

``ContextGraphClient`` — the ergonomic, redacting front door to the bitemporal Context Graph,
behind a :class:`~korchestrator.interfaces.GraphRepository` (P7.5's in-memory default backend).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from korchestrator.interfaces import GraphRepository
from korchestrator.models.context_graph import DecisionNode, EventNode, GraphNode
from korchestrator.security import Shield

__all__ = ["ContextGraphClient"]


class ContextGraphClient:
    """Record and query bitemporal decision/event nodes, tenant-scoped.

    Sits behind a :class:`~korchestrator.interfaces.GraphRepository`. Every write's free-text
    ``content`` is redacted through :class:`~korchestrator.security.Shield`
    before it reaches the repository — governance audit and trace ingestion depend on redaction
    existing (P7.1). Nodes are immutable and append-only (event sourcing): a correction is a new
    node with a later ``transaction_time``, never a mutation of an earlier one, so history stays
    fully queryable for time-travel.

    Args:
        repository: The backing store — :class:`~korchestrator.persistence.InMemoryGraphRepository`
            by default, or any :class:`~korchestrator.interfaces.GraphRepository`.
        redactor: The redactor to run every ``content`` through. Defaults to a fresh
            :class:`~korchestrator.security.Shield`.

    Example:
        >>> import asyncio
        >>> from datetime import datetime, timezone
        >>> from korchestrator.persistence import ContextGraphClient, InMemoryGraphRepository
        >>> now = datetime(2026, 7, 23, tzinfo=timezone.utc)
        >>> client = ContextGraphClient(InMemoryGraphRepository())
        >>> async def record_and_query():
        ...     await client.record_decision(
        ...         tenant_id="acme", content="Escalate to a human reviewer",
        ...         provenance="lead", valid_time=now, transaction_time=now,
        ...     )
        ...     return await client.query(tenant_id="acme")
        >>> [node.kind for node in asyncio.run(record_and_query())]
        ['decision']
    """

    def __init__(self, repository: GraphRepository, *, redactor: Shield | None = None) -> None:
        """Store the backing repository and the (optionally injected) redactor."""
        self._repository = repository
        self._redactor = redactor or Shield()

    async def record_decision(
        self,
        *,
        tenant_id: str,
        content: str,
        provenance: str,
        valid_time: datetime,
        transaction_time: datetime,
        run_id: str | None = None,
        confidence: float = 1.0,
        rationale: str | None = None,
    ) -> DecisionNode:
        """Record a decision the swarm (or an operator) made; ``content`` is redacted first."""
        node = DecisionNode(
            id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            run_id=run_id,
            content=self._redactor.redact(content).text,
            provenance=provenance,
            confidence=confidence,
            rationale=rationale,
            valid_time=valid_time,
            transaction_time=transaction_time,
        )
        await self._repository.record_node(node, tenant_id=tenant_id)
        return node

    async def record_event(
        self,
        *,
        tenant_id: str,
        content: str,
        provenance: str,
        event_type: str,
        valid_time: datetime,
        transaction_time: datetime,
        run_id: str | None = None,
        confidence: float = 1.0,
    ) -> EventNode:
        """Record something that happened (a message, a tool call, a governance decision)."""
        node = EventNode(
            id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            run_id=run_id,
            content=self._redactor.redact(content).text,
            provenance=provenance,
            event_type=event_type,
            confidence=confidence,
            valid_time=valid_time,
            transaction_time=transaction_time,
        )
        await self._repository.record_node(node, tenant_id=tenant_id)
        return node

    async def query(
        self,
        *,
        tenant_id: str,
        run_id: str | None = None,
        as_of: datetime | None = None,
        valid_at: datetime | None = None,
    ) -> tuple[GraphNode, ...]:
        """Return tenant-scoped nodes, oldest-first, with time-travel.

        ``as_of`` keeps only nodes recorded at or before that ``transaction_time`` — "what did we
        know as of this recording time." ``valid_at`` keeps only nodes true at or before that
        ``valid_time`` — "what was true as of this moment." Both may be combined with each other
        and with ``run_id``.
        """
        return await self._repository.query_nodes(
            tenant_id=tenant_id, run_id=run_id, as_of=as_of, valid_at=valid_at
        )
