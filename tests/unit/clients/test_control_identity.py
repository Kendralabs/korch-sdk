"""KorchestratorClient control + identity tests (spec 04 §7.3, P9.4)."""

from __future__ import annotations

import json as json_module

import httpx
import pytest
import respx

from korchestrator.clients import KorchestratorClient
from korchestrator.exceptions import ApiError
from korchestrator.models import RunStatus

BASE_URL = "https://engine.example.com"
STARTED_AT = "2026-07-23T00:00:00+00:00"


def _run_body(*, status: object = "governance_paused", **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "run_id": "r1",
        "status": status,
        "final_answer": "",
        "supersteps": 0,
        "trust_score": 1.0,
        "message_count": 0,
        "started_at": STARTED_AT,
    }
    body.update(overrides)
    return body


# --- resume / cancel / edit_resume ---------------------------------------------------------------


@respx.mock
def test_resume_posts_and_returns_the_updated_result() -> None:
    respx.post(f"{BASE_URL}/v1/run/r1/resume").mock(
        return_value=httpx.Response(200, json=_run_body(status="running"))
    )
    client = KorchestratorClient(BASE_URL)
    result = client.resume("r1")
    assert result.status is RunStatus.RUNNING
    client.close()


@respx.mock
def test_cancel_posts_and_returns_the_updated_result() -> None:
    respx.post(f"{BASE_URL}/v1/run/r1/cancel").mock(
        return_value=httpx.Response(200, json=_run_body(status="cancelled"))
    )
    client = KorchestratorClient(BASE_URL)
    result = client.cancel("r1")
    assert result.status is RunStatus.CANCELLED
    client.close()


@respx.mock
def test_edit_resume_sends_updates_and_trust_delta() -> None:
    route = respx.post(f"{BASE_URL}/v1/run/r1/edit-resume").mock(
        return_value=httpx.Response(200, json=_run_body(status="running"))
    )
    client = KorchestratorClient(BASE_URL)
    result = client.edit_resume("r1", updates={"note": "approved"}, trust_delta=0.2)
    assert result.status is RunStatus.RUNNING
    sent = json_module.loads(route.calls.last.request.content)
    assert sent == {"updates": {"note": "approved"}, "trust_delta": 0.2}
    client.close()


@respx.mock
def test_edit_resume_defaults_updates_to_an_empty_mapping() -> None:
    route = respx.post(f"{BASE_URL}/v1/run/r1/edit-resume").mock(
        return_value=httpx.Response(200, json=_run_body(status="running"))
    )
    client = KorchestratorClient(BASE_URL)
    client.edit_resume("r1")
    sent = json_module.loads(route.calls.last.request.content)
    assert sent == {"updates": {}, "trust_delta": 0.0}
    client.close()


# --- me / my_quota / my_runs -----------------------------------------------------------------


@respx.mock
def test_me_returns_the_caller_identity() -> None:
    respx.get(f"{BASE_URL}/v1/me").mock(
        return_value=httpx.Response(
            200, json={"tenant_id": "acme", "scopes": ["korchestrator:read"]}
        )
    )
    client = KorchestratorClient(BASE_URL)
    identity = client.me()
    assert identity.tenant_id == "acme"
    assert identity.scopes == ("korchestrator:read",)
    client.close()


@respx.mock
def test_my_quota_returns_the_quota() -> None:
    respx.get(f"{BASE_URL}/v1/me/quota").mock(
        return_value=httpx.Response(200, json={"limit": 100, "used": 40, "remaining": 60})
    )
    client = KorchestratorClient(BASE_URL)
    quota = client.my_quota()
    assert quota.limit == 100
    assert quota.remaining == 60
    client.close()


@respx.mock
def test_my_runs_parses_a_bare_array() -> None:
    respx.get(f"{BASE_URL}/v1/me/runs").mock(
        return_value=httpx.Response(
            200, json=[{"run_id": "r1", "status": "completed", "superstep": 2}]
        )
    )
    client = KorchestratorClient(BASE_URL)
    runs = client.my_runs()
    assert [r.run_id for r in runs] == ["r1"]
    client.close()


@respx.mock
def test_my_runs_rejects_an_unexpected_shape() -> None:
    respx.get(f"{BASE_URL}/v1/me/runs").mock(return_value=httpx.Response(200, json={"oops": True}))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.my_runs()
    client.close()


# --- key management ---------------------------------------------------------------------------


@respx.mock
def test_create_key_returns_the_secret_once() -> None:
    route = respx.post(f"{BASE_URL}/v1/keys").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "key-1",
                "key": "sk-brand-new-secret",
                "scopes": ["korchestrator:read"],
                "created_at": STARTED_AT,
            },
        )
    )
    client = KorchestratorClient(BASE_URL)
    key = client.create_key(scopes=["korchestrator:read"])
    assert key.id == "key-1"
    assert key.key.get_secret_value() == "sk-brand-new-secret"
    assert "sk-brand-new-secret" not in repr(key)  # SecretStr redacts by default
    sent = json_module.loads(route.calls.last.request.content)
    assert sent == {"scopes": ["korchestrator:read"]}
    client.close()


@respx.mock
def test_list_keys_never_carries_a_secret_field() -> None:
    respx.get(f"{BASE_URL}/v1/keys").mock(
        return_value=httpx.Response(
            200, json={"keys": [{"id": "key-1", "scopes": [], "created_at": STARTED_AT}]}
        )
    )
    client = KorchestratorClient(BASE_URL)
    (key,) = client.list_keys()
    assert key.id == "key-1"
    client.close()


@respx.mock
def test_revoke_key_sends_a_delete_and_returns_none() -> None:
    route = respx.delete(f"{BASE_URL}/v1/keys/key-1").mock(return_value=httpx.Response(204))
    client = KorchestratorClient(BASE_URL)
    assert client.revoke_key("key-1") is None
    assert route.called
    client.close()
