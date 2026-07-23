"""Contract layer. Imports: korchestrator.models, stdlib.

The ``GraphRepository`` and ``TenantStore`` supporting protocols — read/write the context graph
and scope tenant data. Every method is tenant-scoped; a call without a tenant is a defect.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from korchestrator.models.context_graph import GraphNode
from korchestrator.models.state import AgentState

__all__ = ["GraphRepository", "TenantStore"]


@runtime_checkable
class GraphRepository(Protocol):
    """Persist and retrieve run state and Context Graph nodes, always scoped by tenant.

    Implementations: an in-memory backend (the default; ``PERSISTENCE_BACKEND=memory``), a mock,
    and external backends post-1.0. ``PERSISTENCE_BACKEND=none`` runs fully standalone.

    Concurrency: implementations MUST be safe for concurrent reads and writes. ``tenant_id`` is
    mandatory on every call and MUST scope the data — cross-tenant access is a defect.

    ``save_state``/``load_state`` (P1) checkpoint run state; ``record_node``/``query_nodes``
    (P7.6) are the bitemporal decision/event node API the Context Graph client
    (``persistence.ContextGraphClient``) is layered on — the extension the P1 docstring
    anticipated ("layered on this protocol when it lands").
    """

    async def save_state(self, state: AgentState, *, tenant_id: str) -> None:
        """Persist ``state`` under its ``run_id`` within ``tenant_id``."""
        ...

    async def load_state(self, run_id: str, *, tenant_id: str) -> AgentState | None:
        """Return the latest saved state for ``run_id`` in ``tenant_id``, or ``None`` if absent."""
        ...

    async def record_node(self, node: GraphNode, *, tenant_id: str) -> None:
        """Append an immutable :class:`GraphNode` (event sourcing — nodes are never overwritten)."""
        ...

    async def query_nodes(
        self,
        *,
        tenant_id: str,
        run_id: str | None = None,
        as_of: datetime | None = None,
        valid_at: datetime | None = None,
    ) -> tuple[GraphNode, ...]:
        """Return tenant-scoped nodes, optionally filtered by ``run_id`` and time-travelled.

        ``as_of`` keeps only nodes recorded at or before that ``transaction_time`` ("what did we
        know as of this recording time"); ``valid_at`` keeps only nodes true at or before that
        ``valid_time`` ("what was true as of this moment"). Both may be combined.
        """
        ...


@runtime_checkable
class TenantStore(Protocol):
    """Resolve and scope tenant data.

    Default implementation: an in-memory store. Used to validate that a ``tenant_id`` is known
    before data is scoped to it.
    """

    async def is_known(self, tenant_id: str) -> bool:
        """Return whether ``tenant_id`` is a recognised tenant."""
        ...
