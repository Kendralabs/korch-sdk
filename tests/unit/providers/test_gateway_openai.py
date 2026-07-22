"""Unit tests for the networked OpenAIGateway (spec 03 §5, spec 08 §2.2, P4.3).

HTTP is mocked with ``respx`` against the documented OpenAI-compatible contract — no network, no
real model, no credentials. These require the ``[remote]`` extra (httpx) and the ``[dev]`` extra
(respx); the base-install job skips them.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

httpx = pytest.importorskip("httpx")
respx = pytest.importorskip("respx")

from korchestrator.exceptions import (  # noqa: E402 — after importorskip guards
    AuthError,
    ProviderError,
    RateLimitError,
    TimeoutError,  # noqa: A004 — the KorchError timeout, not the builtin
    ValidationError,
)
from korchestrator.interfaces import IModelGateway  # noqa: E402
from korchestrator.models.state import Message, MessageRole  # noqa: E402
from korchestrator.providers import OpenAIGateway  # noqa: E402

BASE_URL = "https://api.openai.test/v1"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _gateway() -> OpenAIGateway:
    return OpenAIGateway(api_key="sk-test", base_url=BASE_URL, timeout_seconds=5.0)


def _msg(content: str) -> Message:
    return Message(
        id="m", sender="user", role=MessageRole.USER, content=content, superstep=0, valid_time=NOW
    )


def _completion(content: str) -> dict[str, object]:
    return {"id": "chatcmpl-1", "choices": [{"message": {"role": "assistant", "content": content}}]}


def test_conforms_to_the_model_gateway_port() -> None:
    assert isinstance(_gateway(), IModelGateway)


def test_requires_injected_credentials_and_endpoint() -> None:
    with pytest.raises(ValidationError):
        OpenAIGateway(api_key="", base_url=BASE_URL)
    with pytest.raises(ValidationError):
        OpenAIGateway(api_key="sk-test", base_url="")


@respx.mock
async def test_completion_maps_the_assistant_reply_to_a_message() -> None:
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_completion("the answer"))
    )
    result = await _gateway().complete([_msg("the question")], model="gpt-4o")
    assert result.content == "the answer"
    assert result.role is MessageRole.ASSISTANT
    # The request carried the injected credential and the mapped chat message.
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer sk-test"


@respx.mock
async def test_max_tokens_is_forwarded_only_when_set() -> None:
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_completion("ok"))
    )
    await _gateway().complete([_msg("q")], model="gpt-4o", max_tokens=64)
    import json

    assert json.loads(route.calls.last.request.content)["max_tokens"] == 64


@respx.mock
async def test_timeout_becomes_a_korch_timeout_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(side_effect=httpx.ConnectTimeout)
    with pytest.raises(TimeoutError) as excinfo:
        await _gateway().complete([_msg("q")], model="gpt-4o")
    assert excinfo.value.__cause__ is not None


@respx.mock
async def test_unauthorized_becomes_auth_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(return_value=httpx.Response(401))
    with pytest.raises(AuthError):
        await _gateway().complete([_msg("q")], model="gpt-4o")


@respx.mock
async def test_rate_limited_becomes_rate_limit_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(return_value=httpx.Response(429))
    with pytest.raises(RateLimitError):
        await _gateway().complete([_msg("q")], model="gpt-4o")


@respx.mock
async def test_server_error_becomes_provider_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderError) as excinfo:
        await _gateway().complete([_msg("q")], model="gpt-4o")
    # The spec 08 §2.2 wrapping shape: a stable non-empty code and a preserved __cause__.
    assert excinfo.value.code
    assert excinfo.value.__cause__ is not None


@respx.mock
async def test_unexpected_response_shape_becomes_provider_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json={"unexpected": True})
    )
    with pytest.raises(ProviderError):
        await _gateway().complete([_msg("q")], model="gpt-4o")


@respx.mock
async def test_available_models_lists_cards_from_the_models_endpoint() -> None:
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "gpt-4o", "owned_by": "openai"}, {"object": "malformed"}]},
        )
    )
    cards = await _gateway().available_models()
    assert [card.name for card in cards] == ["gpt-4o"]
    assert cards[0].provider == "openai"


@respx.mock
async def test_vendor_error_never_leaks_from_available_models() -> None:
    respx.get(f"{BASE_URL}/models").mock(return_value=httpx.Response(503))
    with pytest.raises(ProviderError):
        await _gateway().available_models()


@respx.mock
async def test_connection_error_becomes_provider_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(side_effect=httpx.ConnectError)
    with pytest.raises(ProviderError):
        await _gateway().complete([_msg("q")], model="gpt-4o")


@respx.mock
async def test_non_json_body_becomes_provider_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, text="not json at all")
    )
    with pytest.raises(ProviderError):
        await _gateway().complete([_msg("q")], model="gpt-4o")


@respx.mock
async def test_non_mapping_body_becomes_provider_error() -> None:
    respx.post(f"{BASE_URL}/chat/completions").mock(return_value=httpx.Response(200, json=[1, 2]))
    with pytest.raises(ProviderError):
        await _gateway().complete([_msg("q")], model="gpt-4o")


@respx.mock
async def test_available_models_timeout_becomes_timeout_error() -> None:
    respx.get(f"{BASE_URL}/models").mock(side_effect=httpx.ReadTimeout)
    with pytest.raises(TimeoutError):
        await _gateway().available_models()


@respx.mock
async def test_available_models_rejects_a_non_list_payload() -> None:
    respx.get(f"{BASE_URL}/models").mock(return_value=httpx.Response(200, json={"data": "nope"}))
    with pytest.raises(ProviderError):
        await _gateway().available_models()


@respx.mock
async def test_available_models_non_json_becomes_provider_error() -> None:
    respx.get(f"{BASE_URL}/models").mock(return_value=httpx.Response(200, text="not json"))
    with pytest.raises(ProviderError):
        await _gateway().available_models()


@respx.mock
async def test_available_models_connection_error_becomes_provider_error() -> None:
    respx.get(f"{BASE_URL}/models").mock(side_effect=httpx.ConnectError)
    with pytest.raises(ProviderError):
        await _gateway().available_models()
