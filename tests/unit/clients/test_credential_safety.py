"""Credential safety tests (spec 04 §7.2, P9.2): never logged, written to disk, or leaked.

``clients/`` currently makes no logging or telemetry calls of its own — P9.3+ add the endpoint
methods that will eventually call the transport under real traffic. These tests lock the
guarantees now, structurally, so a later addition can't quietly regress them: the client's own
``repr``, httpx's header redaction it relies on, and every error path this module can already
raise never surface the API key.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")
respx = pytest.importorskip("respx")

from korchestrator.clients import KorchestratorClient  # noqa: E402 — after importorskip guards
from korchestrator.exceptions import ApiError, NetworkError  # noqa: E402
from korchestrator.exceptions import TimeoutError as KorchTimeoutError  # noqa: E402

BASE_URL = "https://engine.example.com"
SECRET_API_KEY = "sk-super-secret-do-not-leak"  # noqa: S105 — test fixture value, not a real key


@pytest.fixture(autouse=True)
def _no_real_sleep() -> None:
    from unittest import mock

    with mock.patch("korchestrator.clients.client.asyncio.sleep", new_callable=mock.AsyncMock):
        yield


# --- repr / str -----------------------------------------------------------------------------


def test_client_repr_never_contains_the_api_key() -> None:
    client = KorchestratorClient(BASE_URL, api_key=SECRET_API_KEY)
    assert SECRET_API_KEY not in repr(client)
    assert SECRET_API_KEY not in str(client)
    assert BASE_URL in repr(client)
    client.close()


def test_underlying_httpx_headers_repr_redacts_the_authorization_value() -> None:
    # Load-bearing assumption: our own class never repr's raw headers, and relies on httpx's
    # Headers.__repr__ masking `authorization` if anything else ever does. Pin that behaviour so
    # a future httpx upgrade that changes it fails loudly here, not silently in production.
    client = KorchestratorClient(BASE_URL, api_key=SECRET_API_KEY)
    assert SECRET_API_KEY not in repr(client._client.headers)
    assert "[secure]" in repr(client._client.headers).lower() or "secure" in repr(
        client._client.headers
    )
    client.close()


# --- exception paths never leak the key --------------------------------------------------------


@respx.mock
async def test_api_error_never_contains_the_api_key() -> None:
    respx.get(f"{BASE_URL}/v1/me").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    client = KorchestratorClient(BASE_URL, api_key=SECRET_API_KEY)
    with pytest.raises(ApiError) as info:
        await client._request("GET", "/v1/me")
    assert SECRET_API_KEY not in str(info.value)
    assert SECRET_API_KEY not in info.value.message
    assert SECRET_API_KEY not in repr(info.value)
    await client.aclose()


@respx.mock
async def test_network_error_never_contains_the_api_key() -> None:
    respx.get(f"{BASE_URL}/v1/me").mock(side_effect=httpx.ConnectError("refused"))
    client = KorchestratorClient(BASE_URL, api_key=SECRET_API_KEY, max_retries=0)
    with pytest.raises(NetworkError) as info:
        await client._request("GET", "/v1/me")
    assert SECRET_API_KEY not in str(info.value)
    await client.aclose()


@respx.mock
async def test_timeout_error_never_contains_the_api_key() -> None:
    respx.get(f"{BASE_URL}/v1/me").mock(side_effect=httpx.ConnectTimeout("timed out"))
    client = KorchestratorClient(BASE_URL, api_key=SECRET_API_KEY, max_retries=0)
    with pytest.raises(KorchTimeoutError) as info:
        await client._request("GET", "/v1/me")
    assert SECRET_API_KEY not in str(info.value)
    await client.aclose()


@respx.mock
async def test_an_engine_response_that_echoes_the_auth_header_is_not_trusted_into_the_message() -> (
    None
):
    # A misbehaving/compromised engine could echo request headers back in an error body; our
    # message-building must not blindly trust engine-supplied fields containing the header name
    # in a way that would make this worse — only `message`/`code`/`trace_id` are ever read.
    respx.get(f"{BASE_URL}/v1/me").mock(
        return_value=httpx.Response(
            400,
            json={
                "message": "bad request",
                "echo_headers": {"authorization": f"Bearer {SECRET_API_KEY}"},
            },
        )
    )
    client = KorchestratorClient(BASE_URL, api_key=SECRET_API_KEY)
    with pytest.raises(ApiError) as info:
        await client._request("GET", "/v1/me")
    assert SECRET_API_KEY not in str(info.value)
    await client.aclose()


# --- never written to disk -----------------------------------------------------------------------


def test_clients_module_source_never_opens_a_file() -> None:
    # Spec 04 §7.2: credentials must never be written to disk by the SDK. clients/ does no file
    # I/O at all today; this fails loudly if that ever changes without an explicit safety review.
    src_root = Path(__file__).resolve().parents[3] / "src" / "korchestrator" / "clients"
    assert src_root.is_dir()
    for path in src_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "open", f"unexpected file I/O in {path}"
