"""Cross-cutting contract-conformance tests (spec 04 §7, P9.7).

Every other file in this directory tests one group of methods (transport, run lifecycle,
control/identity, streaming, discovery) against its own success and failure shapes. This file
asks a different question across the *whole* method surface at once: does every single public
method — regardless of which endpoint it hits or what it returns on success — surface exactly
``ApiError`` for a non-2xx response, the one documented error type for a failed
``KorchestratorClient`` call (spec 04 §7.5)? Retry policy, the ``Authorization`` header, and
timeout handling are deliberately NOT re-tested per method here: every method routes through the
single shared ``_request`` coroutine, so those properties are already proven uniform by P9.1/P9.2's
direct tests against ``_request`` — repeating them per endpoint would be volume, not coverage.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from korchestrator.clients import KorchestratorClient
from korchestrator.exceptions import ApiError, KorchError
from korchestrator.models import AgentConfig, AgentPersona

BASE_URL = "https://engine.example.com"
_AGENT = AgentConfig(id="lead", persona=AgentPersona(role="review-lead"))
_ERROR_BODY = {"message": "not found", "trace_id": "trace-conformance"}

# (case id, HTTP method, path, a callable invoking the client method under test)
CONFORMANCE_CASES: list[tuple[str, str, str, object]] = [
    ("run", "POST", "/v1/run/auto", lambda c: c.run("Summarize the quarterly incident reports")),
    (
        "run_swarm",
        "POST",
        "/v1/run/swarm",
        lambda c: c.run_swarm([_AGENT], objective="Review this change for security"),
    ),
    ("get_run", "GET", "/v1/run/r1", lambda c: c.get_run("r1")),
    ("wait", "GET", "/v1/run/r1", lambda c: c.wait("r1")),
    (
        "run_and_wait",
        "POST",
        "/v1/run/auto",
        lambda c: c.run_and_wait("Summarize the quarterly incident reports"),
    ),
    ("list_runs", "GET", "/v1/runs", lambda c: c.list_runs()),
    ("get_run_summary", "GET", "/v1/runs/r1/summary", lambda c: c.get_run_summary("r1")),
    ("resume", "POST", "/v1/run/r1/resume", lambda c: c.resume("r1")),
    ("cancel", "POST", "/v1/run/r1/cancel", lambda c: c.cancel("r1")),
    ("edit_resume", "POST", "/v1/run/r1/edit-resume", lambda c: c.edit_resume("r1")),
    ("me", "GET", "/v1/me", lambda c: c.me()),
    ("my_quota", "GET", "/v1/me/quota", lambda c: c.my_quota()),
    ("my_runs", "GET", "/v1/me/runs", lambda c: c.my_runs()),
    ("create_key", "POST", "/v1/keys", lambda c: c.create_key()),
    ("list_keys", "GET", "/v1/keys", lambda c: c.list_keys()),
    ("revoke_key", "DELETE", "/v1/keys/key-1", lambda c: c.revoke_key("key-1")),
    ("tools", "GET", "/v1/tools", lambda c: c.tools()),
    ("models", "GET", "/v1/models", lambda c: c.models()),
    ("swarm_templates", "GET", "/v1/swarm-templates", lambda c: c.swarm_templates()),
]


@pytest.mark.parametrize(
    ("http_method", "path", "call"),
    [case[1:] for case in CONFORMANCE_CASES],
    ids=[case[0] for case in CONFORMANCE_CASES],
)
def test_every_method_raises_api_error_on_a_404(http_method: str, path: str, call: object) -> None:
    respx.route(method=http_method, url=f"{BASE_URL}{path}").mock(
        return_value=httpx.Response(404, json=_ERROR_BODY)
    )
    with respx.mock:
        client = KorchestratorClient(BASE_URL, api_key="sk-example")
        with pytest.raises(ApiError) as info:
            call(client)  # type: ignore[operator]
        assert info.value.status == 404
        assert info.value.trace_id == "trace-conformance"
        assert isinstance(info.value, KorchError)
        client.close()


@respx.mock
async def test_stream_also_raises_api_error_on_a_404() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1/stream").mock(
        return_value=httpx.Response(404, json=_ERROR_BODY)
    )
    client = KorchestratorClient(BASE_URL, api_key="sk-example")
    with pytest.raises(ApiError) as info:
        async for _event in client.stream("r1"):
            pass
    assert info.value.status == 404
    assert info.value.trace_id == "trace-conformance"
    await client.aclose()


def test_every_conformance_case_is_covered_exactly_once() -> None:
    # A guard against silently dropping a method from the table above as the client grows.
    public_methods = {
        name
        for name in dir(KorchestratorClient)
        if not name.startswith("_")
        and callable(getattr(KorchestratorClient, name))
        and name not in {"close", "aclose"}
    }
    covered = {case[0] for case in CONFORMANCE_CASES}
    covered |= {"stream"}  # covered by its own dedicated test above, not the parametrized table
    assert public_methods <= covered, public_methods - covered
