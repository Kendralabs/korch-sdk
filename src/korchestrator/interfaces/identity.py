"""Contract layer. Imports: stdlib.

The ``IIdentityProvider`` ARI port — authenticate an agent, resolve it to a decentralised
identifier (DID), and expose its tenant scope.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["IIdentityProvider"]


@runtime_checkable
class IIdentityProvider(Protocol):
    """Authenticate an agent and resolve it to a DID within a tenant scope.

    ARI port. Default implementation: ``providers/identity_local.py`` — an unsecured,
    single-tenant provider that MUST log a WARNING on construction and MUST be rejected under a
    durable multi-tenant deployment (spec 08 §5); an enterprise deployment supplies KIAM / KACP.

    Concurrency: implementations MUST be safe to call concurrently. Tenant scope is mandatory
    data — it is passed in and enforced, never inferred from a client-supplied field.

    Note: the P1 contract is intentionally minimal; a richer identity model may be introduced,
    via an ADR, when the enterprise provider lands.
    """

    async def authenticate(self, agent_id: str, *, tenant_id: str = "default") -> str:
        """Authenticate ``agent_id`` in ``tenant_id`` and return its resolved DID."""
        ...

    def tenant_of(self, agent_id: str) -> str:
        """Return the tenant this agent is scoped to."""
        ...
