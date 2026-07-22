"""Unit tests for the deterministic MockLM gateway (spec 03 §4, spec 09 §4, P4.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.interfaces import IModelGateway
from korchestrator.models.state import Message, MessageRole
from korchestrator.providers import MockLM

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _msg(content: str) -> Message:
    return Message(id="m", sender="user", content=content, superstep=0, valid_time=NOW)


def test_mock_lm_conforms_to_the_model_gateway_port() -> None:
    assert isinstance(MockLM(), IModelGateway)


async def test_completion_is_deterministic() -> None:
    gateway = MockLM()
    first = await gateway.complete([_msg("Summarize the report")], model="gpt-4o")
    second = await gateway.complete([_msg("Summarize the report")], model="gpt-4o")
    assert first.content == second.content
    assert first.role is MessageRole.ASSISTANT


async def test_scripted_response_wins() -> None:
    gateway = MockLM(responses={"gpt-4o-mini": "the scripted summary"})
    result = await gateway.complete([_msg("anything")], model="gpt-4o-mini")
    assert result.content == "the scripted summary"


async def test_default_response_applies_to_unscripted_models() -> None:
    gateway = MockLM(responses={"a": "x"}, default_response="the default")
    assert (await gateway.complete([_msg("q")], model="b")).content == "the default"


async def test_echo_fallback_reflects_the_last_message() -> None:
    result = await MockLM().complete([_msg("hello world")], model="m")
    assert "hello world" in result.content


async def test_call_log_records_each_call() -> None:
    gateway = MockLM()
    await gateway.complete([_msg("one")], model="a")
    await gateway.complete([_msg("two")], model="b")
    assert [call.model for call in gateway.calls] == ["a", "b"]
    assert gateway.calls[0].messages[0].content == "one"


async def test_available_models_returns_the_mock_card() -> None:
    cards = await MockLM().available_models()
    assert [card.name for card in cards] == ["mock-model"]
    assert cards[0].provider == "mock"
