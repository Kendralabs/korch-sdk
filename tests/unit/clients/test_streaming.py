"""KorchestratorClient SSE streaming tests (spec 04 §7.3/§7.5, P9.5)."""

from __future__ import annotations

from unittest import mock

import httpx
import pytest
import respx

from korchestrator.clients import KorchestratorClient
from korchestrator.clients.client import _iter_sse_events, _parse_sse_data
from korchestrator.exceptions import ApiError, NetworkError
from korchestrator.exceptions import TimeoutError as KorchTimeoutError
from korchestrator.models import RunEvent

BASE_URL = "https://engine.example.com"


@pytest.fixture(autouse=True)
def _no_real_sleep() -> mock.AsyncMock:
    with mock.patch("korchestrator.clients.client.asyncio.sleep", new_callable=mock.AsyncMock) as m:
        yield m


def _sse_body(*frames: tuple[str, dict[str, object]]) -> str:
    import json

    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in frames)


# --- happy path -----------------------------------------------------------------------------


@respx.mock
async def test_stream_yields_one_event_per_frame() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1/stream").mock(
        return_value=httpx.Response(
            200,
            text=_sse_body(("thought", {"text": "thinking"}), ("answer", {"text": "done"})),
        )
    )
    client = KorchestratorClient(BASE_URL)
    events = [event async for event in client.stream("r1")]
    assert [e.name for e in events] == ["thought", "answer"]
    assert events[0].payload == {"text": "thinking"}
    assert all(e.run_id == "r1" for e in events)
    await client.aclose()


@respx.mock
async def test_stream_ends_when_the_engine_closes_the_connection() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1/stream").mock(
        return_value=httpx.Response(200, text=_sse_body(("completed", {})))
    )
    client = KorchestratorClient(BASE_URL)
    seen = 0
    async for _event in client.stream("r1"):
        seen += 1
    assert seen == 1
    await client.aclose()


# --- non-2xx / malformed frames --------------------------------------------------------------


@respx.mock
async def test_stream_raises_api_error_on_a_non_2xx_response() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1/stream").mock(
        return_value=httpx.Response(404, json={"message": "run not found"})
    )
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        async for _event in client.stream("r1"):
            pass
    await client.aclose()


def test_parse_sse_data_rejects_non_json() -> None:
    with pytest.raises(ApiError):
        _parse_sse_data("not json")


def test_parse_sse_data_rejects_a_non_object_json_value() -> None:
    with pytest.raises(ApiError):
        _parse_sse_data("[1, 2, 3]")


def test_parse_sse_data_treats_an_empty_payload_as_an_empty_mapping() -> None:
    assert _parse_sse_data("") == {}


# --- frame parsing (direct) --------------------------------------------------------------------


async def test_iter_sse_events_defaults_the_event_name_to_message() -> None:
    async def _lines() -> object:
        for line in ['data: {"a": 1}', ""]:
            yield line

    events = [e async for e in _iter_sse_events(_FakeResponse(_lines()), run_id="r1")]
    assert events == [RunEvent(run_id="r1", name="message", payload={"a": 1})]


async def test_iter_sse_events_ignores_a_trailing_blank_line_with_no_data() -> None:
    async def _lines() -> object:
        for line in ["event: thought", 'data: {"a": 1}', "", ""]:
            yield line

    events = [e async for e in _iter_sse_events(_FakeResponse(_lines()), run_id="r1")]
    assert len(events) == 1


class _FakeResponse:
    def __init__(self, lines: object) -> None:
        self._lines = lines

    def aiter_lines(self) -> object:
        return self._lines


# --- reconnect semantics -----------------------------------------------------------------------


@respx.mock
async def test_stream_reconnects_after_a_dropped_connection(
    _no_real_sleep: mock.AsyncMock,
) -> None:
    route = respx.get(f"{BASE_URL}/v1/run/r1/stream").mock(
        side_effect=[
            httpx.ConnectError("dropped"),
            httpx.Response(200, text=_sse_body(("completed", {}))),
        ]
    )
    client = KorchestratorClient(BASE_URL)
    events = [event async for event in client.stream("r1")]
    assert [e.name for e in events] == ["completed"]
    assert route.call_count == 2
    _no_real_sleep.assert_awaited_once()
    await client.aclose()


@respx.mock
async def test_stream_gives_up_after_max_retries_connection_errors(
    _no_real_sleep: mock.AsyncMock,
) -> None:
    respx.get(f"{BASE_URL}/v1/run/r1/stream").mock(side_effect=httpx.ConnectError("refused"))
    client = KorchestratorClient(BASE_URL, max_retries=1)
    with pytest.raises(NetworkError):
        async for _event in client.stream("r1"):
            pass
    await client.aclose()


@respx.mock
async def test_stream_gives_up_after_max_retries_timeouts(
    _no_real_sleep: mock.AsyncMock,
) -> None:
    respx.get(f"{BASE_URL}/v1/run/r1/stream").mock(side_effect=httpx.ConnectTimeout("timed out"))
    client = KorchestratorClient(BASE_URL, max_retries=1)
    with pytest.raises(KorchTimeoutError):
        async for _event in client.stream("r1"):
            pass
    await client.aclose()
