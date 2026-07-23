"""Context layer (L3).

Imports: korchestrator.interfaces, korchestrator.models, stdlib.

The in-memory ``GraphRepository`` — the default, zero-infrastructure backend for run-state
persistence (spec 05 §1, P1's ``GraphRepository`` protocol) and Context Graph nodes (P7.6).
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from korchestrator.models.context_graph import GraphNode
from korchestrator.models.state import AgentState

__all__ = ["InMemoryGraphRepository"]


class InMemoryGraphRepository:
    """Persist run state and Context Graph nodes in-process, tenant-scoped.

    Stores :class:`~korchestrator.models.state.AgentState` and
    :class:`~korchestrator.models.context_graph.GraphNode`. Implements the
    :class:`~korchestrator.interfaces.GraphRepository` protocol structurally (no
    inheritance needed — the protocol is ``@runtime_checkable``). Not durable across process
    restarts; that is the point — it is the zero-infrastructure default (``PERSISTENCE_BACKEND=
    memory``) that needs no external service, giving the local runtime a best-effort checkpoint
    after each superstep even though the runtime itself has no built-in durability. Safe for
    concurrent reads and writes (an ``asyncio.Lock`` per instance), as the protocol requires.

    Example:
        >>> import asyncio
        >>> from datetime import datetime, timezone
        >>> from korchestrator.models.state import AgentState
        >>> from korchestrator.persistence import InMemoryGraphRepository
        >>> repo = InMemoryGraphRepository()
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report",
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> async def round_trip():
        ...     await repo.save_state(state, tenant_id="acme")
        ...     return await repo.load_state("r1", tenant_id="acme")
        >>> asyncio.run(round_trip()) == state
        True
    """

    def __init__(self) -> None:
        """Start with no saved runs or Context Graph nodes."""
        self._by_tenant: dict[str, dict[str, AgentState]] = {}
        self._nodes_by_tenant: dict[str, list[GraphNode]] = {}
        self._lock = asyncio.Lock()

    async def save_state(self, state: AgentState, *, tenant_id: str) -> None:
        """Persist ``state`` under its ``run_id`` within ``tenant_id``, replacing any prior save."""
        async with self._lock:
            self._by_tenant.setdefault(tenant_id, {})[state.run_id] = state

    async def load_state(self, run_id: str, *, tenant_id: str) -> AgentState | None:
        """Return the latest saved state for ``run_id`` in ``tenant_id``, or ``None`` if absent."""
        async with self._lock:
            return self._by_tenant.get(tenant_id, {}).get(run_id)

    async def record_node(self, node: GraphNode, *, tenant_id: str) -> None:
        """Append ``node`` within ``tenant_id`` — never overwritten (event sourcing)."""
        async with self._lock:
            self._nodes_by_tenant.setdefault(tenant_id, []).append(node)

    async def query_nodes(
        self,
        *,
        tenant_id: str,
        run_id: str | None = None,
        as_of: datetime | None = None,
        valid_at: datetime | None = None,
    ) -> tuple[GraphNode, ...]:
        """Return tenant-scoped nodes, oldest-first, filtered by ``run_id``/time-travel bounds."""
        async with self._lock:
            nodes: list[GraphNode] = list(self._nodes_by_tenant.get(tenant_id, []))
        if run_id is not None:
            nodes = [node for node in nodes if node.run_id == run_id]
        if as_of is not None:
            nodes = [node for node in nodes if node.transaction_time <= as_of]
        if valid_at is not None:
            nodes = [node for node in nodes if node.valid_time <= valid_at]
        return tuple(nodes)
