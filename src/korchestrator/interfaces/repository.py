"""Contract layer. Imports: korchestrator.models, stdlib.

The ``GraphRepository`` and ``TenantStore`` supporting protocols — read/write the context graph
and scope tenant data. Every method is tenant-scoped; a call without a tenant is a defect.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from korchestrator.models.state import AgentState

__all__ = ["GraphRepository", "TenantStore"]


@runtime_checkable
class GraphRepository(Protocol):
    """Persist and retrieve run state, always scoped by tenant.

    Implementations: an in-memory backend (the default; ``PERSISTENCE_BACKEND=memory``), a mock,
    and external backends post-1.0. ``PERSISTENCE_BACKEND=none`` runs fully standalone.

    Concurrency: implementations MUST be safe for concurrent reads and writes. ``tenant_id`` is
    mandatory on every call and MUST scope the data — cross-tenant access is a defect.

    Note: the P1 contract covers run-state persistence; the bitemporal decision/event node API of
    the Context Graph (spec 05, P7) is layered on this protocol when it lands.
    """

    async def save_state(self, state: AgentState, *, tenant_id: str) -> None:
        """Persist ``state`` under its ``run_id`` within ``tenant_id``."""
        ...

    async def load_state(self, run_id: str, *, tenant_id: str) -> AgentState | None:
        """Return the latest saved state for ``run_id`` in ``tenant_id``, or ``None`` if absent."""
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
