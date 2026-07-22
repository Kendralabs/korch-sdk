"""Adapter layer. Imports: korchestrator.exceptions, stdlib. No network, no optional dependency.

The default :class:`~korchestrator.interfaces.IIdentityProvider` — ``LocalIdentityProvider``: an
**unsecured, single-tenant** identity provider for local development (spec 03 §5). It authenticates
any agent within its one bound tenant and resolves it to a deterministic synthetic DID. It performs
no real authentication, so it MUST log a warning on construction and MUST be rejected by the
production-boot gate under a durable multi-tenant deployment (spec 08 §5); an enterprise deployment
supplies KIAM / KACP instead.
"""

from __future__ import annotations

import logging

from korchestrator.exceptions import AuthError, ValidationError

__all__ = ["LocalIdentityProvider"]

_logger = logging.getLogger("korchestrator")


class LocalIdentityProvider:
    """Unsecured, single-tenant :class:`~korchestrator.interfaces.IIdentityProvider` for local runs.

    Authenticates any non-empty ``agent_id`` within its one bound tenant and returns a deterministic
    synthetic DID (``did:korch:local:<tenant>:<agent>``). There is **no real authentication**: this
    exists so a fresh install runs with zero identity infrastructure. Cross-tenant access is refused
    — the tenant is enforced, never inferred — but within the tenant every agent is trusted.

    Security: this provider is a development fallback. It logs a warning on construction and the
    production-boot gate rejects it under a durable multi-tenant deployment (spec 08 §5). Supply an
    enterprise ``IIdentityProvider`` (KIAM / KACP) for anything beyond local development.

    Concurrency: safe to call concurrently — it holds only immutable configuration.

    Args:
        tenant_id: The single tenant this provider serves. Defaults to ``"default"``.

    Example:
        >>> import asyncio
        >>> from korchestrator.providers import LocalIdentityProvider
        >>> provider = LocalIdentityProvider()  # doctest: +SKIP
        >>> asyncio.run(provider.authenticate("researcher"))  # doctest: +SKIP
        'did:korch:local:default:researcher'
    """

    def __init__(self, *, tenant_id: str = "default") -> None:
        """Bind the single tenant and warn that this is an unsecured development provider."""
        if not tenant_id:
            raise ValidationError(
                "tenant_id must be a non-empty string identifying the tenant this provider "
                "serves, e.g. 'default'."
            )
        self._tenant_id = tenant_id
        _logger.warning(
            "identity.local.insecure",
            extra={
                "event": "identity.local.insecure",
                "tenant_id": tenant_id,
                "detail": (
                    "LocalIdentityProvider performs no real authentication and serves a single "
                    "tenant; it must not be used in a durable multi-tenant deployment."
                ),
            },
        )

    async def authenticate(self, agent_id: str, *, tenant_id: str = "default") -> str:
        """Authenticate ``agent_id`` within the bound tenant and return its synthetic DID.

        Args:
            agent_id: The agent to authenticate; must be non-empty.
            tenant_id: The tenant the caller claims. It is enforced against the bound tenant, not
                inferred; a mismatch is refused.

        Returns:
            The deterministic DID ``did:korch:local:<tenant>:<agent_id>``.

        Raises:
            ValidationError: If ``agent_id`` is empty.
            AuthError: If ``tenant_id`` is not the tenant this provider is bound to.
        """
        if not agent_id:
            raise ValidationError(
                "agent_id must be a non-empty string identifying the agent to authenticate."
            )
        if tenant_id != self._tenant_id:
            raise AuthError(
                f"LocalIdentityProvider is bound to tenant '{self._tenant_id}' and cannot "
                f"authenticate agent '{agent_id}' in tenant '{tenant_id}'. Construct a provider "
                f"for that tenant, or supply an enterprise identity provider.",
                code="KORCH_AUTH_FORBIDDEN",
            )
        return f"did:korch:local:{self._tenant_id}:{agent_id}"

    def tenant_of(self, agent_id: str) -> str:
        """Return the single tenant this provider is scoped to (every agent lives in it)."""
        return self._tenant_id
