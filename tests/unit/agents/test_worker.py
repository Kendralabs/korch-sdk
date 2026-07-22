"""Unit tests for the DSPy WorkerAgent under MockLM (spec 05 §36, ADR 0013, P4.6)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest import mock

import pytest

from fixtures.fake_clock import FakeClock
from korchestrator.agents import Agent, WorkerAgent
from korchestrator.exceptions import ConfigurationError, MissingExtraError
from korchestrator.models.state import AgentState
from korchestrator.providers import MockLM

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

# A DSPy chat-adapter-formatted reply, as a real model (following the prompt) would produce.
_STRUCTURED = "[[ ## answer ## ]]\n42\n\n[[ ## is_final ## ]]\nTrue\n\n[[ ## completed ## ]]"


def _state(objective: str = "Summarize the incident report clearly") -> AgentState:
    return AgentState(run_id="r1", objective=objective, transaction_time=NOW)


def _clock() -> FakeClock:
    return FakeClock(start=NOW, step_seconds=0)


def test_worker_is_an_agent() -> None:
    assert isinstance(WorkerAgent(id="w", role="analyst"), Agent)


async def test_missing_gateway_raises_configuration_error() -> None:
    agent = WorkerAgent(id="w", role="analyst").bind(clock=_clock())
    with pytest.raises(ConfigurationError):
        await agent.think(_state())


async def test_reasoning_without_dspy_raises_missing_extra() -> None:
    agent = WorkerAgent(id="w", role="analyst").bind(clock=_clock(), gateway=MockLM())
    with mock.patch.dict(sys.modules, {"dspy": None}), pytest.raises(MissingExtraError):
        await agent.think(_state())


async def test_reasoning_under_mock_is_deterministic() -> None:
    pytest.importorskip("dspy")
    agent = WorkerAgent(id="analyst", role="analyst").bind(clock=_clock(), gateway=MockLM())
    first = await agent.think(_state())
    second = await agent.think(_state())
    assert first.agent_id == "analyst"
    assert first.messages[0].content == second.messages[0].content
    assert first.messages[0].sender == "analyst"


async def test_structured_reply_sets_the_answer_and_halts() -> None:
    pytest.importorskip("dspy")
    gateway = MockLM(responses={"m1": _STRUCTURED})
    agent = WorkerAgent(id="w", role="analyst", model="m1").bind(clock=_clock(), gateway=gateway)
    update = await agent.think(_state())
    assert update.messages[0].content == "42"
    assert update.halt is True
    assert update.messages[0].kind == "answer"


async def test_heterogeneous_models_are_honoured() -> None:
    pytest.importorskip("dspy")
    gateway = MockLM()
    a = WorkerAgent(id="a", role="a", model="model-a").bind(clock=_clock(), gateway=gateway)
    b = WorkerAgent(id="b", role="b", model="model-b").bind(clock=_clock(), gateway=gateway)
    await a.think(_state())
    await b.think(_state())
    assert {call.model for call in gateway.calls} == {"model-a", "model-b"}


class _BoomGateway:
    """A gateway whose completion always fails, to exercise the error boundary."""

    async def complete(
        self, messages: object, *, model: str, max_tokens: int | None = None
    ) -> object:
        raise RuntimeError("gateway exploded")

    async def available_models(self) -> list[object]:
        return []


async def test_reasoning_failure_becomes_provider_error() -> None:
    pytest.importorskip("dspy")
    from korchestrator.exceptions import ProviderError

    agent = WorkerAgent(id="w", role="analyst").bind(clock=_clock(), gateway=_BoomGateway())
    with pytest.raises(ProviderError) as excinfo:
        await agent.think(_state())
    assert excinfo.value.__cause__ is not None


async def test_unstructured_reply_falls_back_without_halting() -> None:
    pytest.importorskip("dspy")
    # Default MockLM echo is not field-marked; the lenient adapter puts it in `answer`.
    agent = WorkerAgent(id="w", role="analyst").bind(clock=_clock(), gateway=MockLM())
    update = await agent.think(_state())
    assert update.messages[0].content  # non-empty answer from the echo
    assert update.halt is False  # is_final defaulted False, so the node does not halt
    assert update.messages[0].kind == "answer"  # a worker's contribution is always an answer
