"""Unit tests for the unsecured single-tenant LocalIdentityProvider (spec 03 §5, P4.2)."""

from __future__ import annotations

import logging

import pytest

from korchestrator.exceptions import AuthError, ValidationError
from korchestrator.interfaces import IIdentityProvider
from korchestrator.providers import LocalIdentityProvider


def test_conforms_to_the_identity_port() -> None:
    assert isinstance(LocalIdentityProvider(), IIdentityProvider)


def test_construction_warns_that_it_is_insecure(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="korchestrator"):
        LocalIdentityProvider()
    assert any(record.message == "identity.local.insecure" for record in caplog.records)


def test_empty_tenant_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LocalIdentityProvider(tenant_id="")


async def test_authenticate_returns_a_deterministic_did() -> None:
    provider = LocalIdentityProvider()
    first = await provider.authenticate("researcher")
    second = await provider.authenticate("researcher")
    assert first == second == "did:korch:local:default:researcher"


async def test_authenticate_scopes_the_did_to_the_bound_tenant() -> None:
    provider = LocalIdentityProvider(tenant_id="acme")
    did = await provider.authenticate("worker-1", tenant_id="acme")
    assert did == "did:korch:local:acme:worker-1"


async def test_empty_agent_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        await LocalIdentityProvider().authenticate("")


async def test_cross_tenant_authentication_is_refused() -> None:
    provider = LocalIdentityProvider(tenant_id="acme")
    with pytest.raises(AuthError) as excinfo:
        await provider.authenticate("worker-1", tenant_id="other")
    assert excinfo.value.code == "KORCH_AUTH_FORBIDDEN"


def test_tenant_of_returns_the_bound_tenant() -> None:
    provider = LocalIdentityProvider(tenant_id="acme")
    assert provider.tenant_of("anyone") == "acme"
