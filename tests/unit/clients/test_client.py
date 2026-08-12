"""KorchestratorClient transport tests (spec 04 §7.5, P9.1): auth, timeout, retry, backoff."""

from __future__ import annotations

from unittest import mock

import pytest

httpx = pytest.importorskip("httpx")
respx = pytest.importorskip("respx")

from korchestrator.clients import KorchestratorClient  # noqa: E402 — after importorskip guards
from korchestrator.exceptions import ApiError, NetworkError  # noqa: E402
from korchestrator.exceptions import TimeoutError as KorchTimeoutError  # noqa: E402

BASE_URL = "https://engine.example.com"


@pytest.fixture(autouse=True)
def _no_real_sleep() -> mock.AsyncMock:
    # Backoff jitter must never slow the suite down (T2) — patch the client's own sleep call.
    with mock.patch("korchestrator.clients.client.asyncio.sleep", new_callable=mock.AsyncMock) as m:
        yield m


# --- auth header ----------------------------------------------------------------------------


def test_constructor_sets_the_bearer_header_when_an_api_key_is_given() -> None:
    client = KorchestratorClient(BASE_URL, api_key="sk-example")
    assert client._client.headers["Authorization"] == "Bearer sk-example"
    client.close()


def test_constructor_omits_the_auth_header_without_an_api_key() -> None:
    client = KorchestratorClient(BASE_URL)
    assert "Authorization" not in client._client.headers
    client.close()


def test_constructor_defaults_the_timeout_to_30_seconds() -> None:
    client = KorchestratorClient(BASE_URL)
    assert client._client.timeout.read == 30.0
    client.close()


# --- happy path -------------------------------------------------------------------------------


@respx.mock
async def test_request_returns_the_response_on_success() -> None:
    respx.get(f"{BASE_URL}/v1/me").mock(return_value=httpx.Response(200, json={"tenant": "t1"}))
    client = KorchestratorClient(BASE_URL, api_key="sk-example")
    response = await client._request("GET", "/v1/me")
    assert response.status_code == 200
    assert response.json() == {"tenant": "t1"}
    await client.aclose()


async def test_async_context_manager_closes_on_exit() -> None:
    async with KorchestratorClient(BASE_URL) as client:
        assert not client._client.is_closed
    assert client._client.is_closed


# --- non-retryable errors -----------------------------------------------------------------------


@respx.mock
async def test_a_non_retryable_4xx_raises_api_error_without_retrying() -> None:
    route = respx.get(f"{BASE_URL}/v1/run/bad").mock(
        return_value=httpx.Response(404, json={"message": "run not found", "trace_id": "trace-1"})
    )
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError) as info:
        await client._request("GET", "/v1/run/bad")
    assert route.call_count == 1  # never retried — retrying a client error is a defect
    assert info.value.status == 404
    assert info.value.trace_id == "trace-1"
    assert "run not found" in info.value.message
    await client.aclose()


@respx.mock
async def test_api_error_falls_back_to_response_text_when_the_body_is_not_json() -> None:
    respx.get(f"{BASE_URL}/v1/me").mock(return_value=httpx.Response(400, text="bad request"))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError) as info:
        await client._request("GET", "/v1/me")
    assert info.value.status == 400
    assert "bad request" in info.value.message
    assert info.value.trace_id is None
    await client.aclose()


@respx.mock
async def test_api_error_falls_back_to_response_text_when_the_json_body_has_no_message() -> None:
    respx.get(f"{BASE_URL}/v1/me").mock(return_value=httpx.Response(400, json={"detail": "nope"}))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError) as info:
        await client._request("GET", "/v1/me")
    assert info.value.status == 400
    assert info.value.code == "KORCH_API_ERROR"  # no `code` field in the body -> the default
    assert "detail" in info.value.message  # falls back to the raw text of the JSON body
    await client.aclose()


# --- retryable status codes ----------------------------------------------------------------------


@respx.mock
async def test_a_503_is_retried_and_a_later_success_is_returned(
    _no_real_sleep: mock.AsyncMock,
) -> None:
    route = respx.get(f"{BASE_URL}/v1/me").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    client = KorchestratorClient(BASE_URL)
    response = await client._request("GET", "/v1/me")
    assert response.status_code == 200
    assert route.call_count == 2
    _no_real_sleep.assert_awaited_once()
    await client.aclose()


@pytest.mark.parametrize("status", [429, 502, 503, 504])
@respx.mock
async def test_retryable_statuses_are_retried_up_to_max_retries_then_raise(
    status: int, _no_real_sleep: mock.AsyncMock
) -> None:
    route = respx.get(f"{BASE_URL}/v1/me").mock(return_value=httpx.Response(status))
    client = KorchestratorClient(BASE_URL, max_retries=2)
    with pytest.raises(ApiError) as info:
        await client._request("GET", "/v1/me")
    assert route.call_count == 3  # the original attempt + 2 retries
    assert info.value.status == status
    assert _no_real_sleep.await_count == 2
    await client.aclose()


# --- connection failures -------------------------------------------------------------------------


@respx.mock
async def test_a_connection_error_is_retried_then_wrapped_as_network_error(
    _no_real_sleep: mock.AsyncMock,
) -> None:
    route = respx.get(f"{BASE_URL}/v1/me").mock(side_effect=httpx.ConnectError("refused"))
    client = KorchestratorClient(BASE_URL, max_retries=1)
    with pytest.raises(NetworkError):
        await client._request("GET", "/v1/me")
    assert route.call_count == 2  # the original attempt + 1 retry
    await client.aclose()


@respx.mock
async def test_a_timeout_is_retried_then_wrapped_as_korch_timeout_error(
    _no_real_sleep: mock.AsyncMock,
) -> None:
    route = respx.get(f"{BASE_URL}/v1/me").mock(side_effect=httpx.ConnectTimeout("timed out"))
    client = KorchestratorClient(BASE_URL, max_retries=1)
    with pytest.raises(KorchTimeoutError):
        await client._request("GET", "/v1/me")
    assert route.call_count == 2
    await client.aclose()


# --- non-retryable, non-recoverable ---------------------------------------------------------------


@respx.mock
async def test_a_400_is_never_retried(_no_real_sleep: mock.AsyncMock) -> None:
    route = respx.post(f"{BASE_URL}/v1/run/auto").mock(return_value=httpx.Response(400))
    client = KorchestratorClient(BASE_URL, max_retries=5)
    with pytest.raises(ApiError):
        await client._request("POST", "/v1/run/auto")
    assert route.call_count == 1
    _no_real_sleep.assert_not_awaited()
    await client.aclose()
