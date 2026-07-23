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


# --- ReAct loop (P10.2, ADR 0018) ----------------------------------------------------------------


def _react_reply(
    *, tool_name: str = "", tool_args: str = "", answer: str = "", is_final: bool
) -> str:
    """Build a dspy chat-adapter-formatted ReActWorkerSignature reply."""
    return (
        "[[ ## thought ## ]]\nreasoning\n\n"
        f"[[ ## tool_name ## ]]\n{tool_name}\n\n"
        f"[[ ## tool_args ## ]]\n{tool_args}\n\n"
        f"[[ ## answer ## ]]\n{answer}\n\n"
        f"[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"
    )


class _ScriptedGateway:
    """A gateway returning one scripted reply per call, in order (for multi-step ReAct tests)."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def complete(
        self, messages: object, *, model: str, max_tokens: int | None = None
    ) -> object:
        from korchestrator.models.state import Message, MessageRole

        self.calls += 1
        content = self._replies.pop(0) if self._replies else ""
        return Message(
            id="m",
            role=MessageRole.ASSISTANT,
            sender="mock",
            content=content,
            superstep=0,
            valid_time=NOW,
        )

    async def available_models(self) -> list[object]:
        return []


class _FakeInvoker:
    """A deterministic fake :class:`IToolInvoker` recording every call it received."""

    def __init__(self, output: object = "search result", *, ok: bool = True) -> None:
        self._output = output
        self._ok = ok
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def invoke_tool(
        self, tool: str, args: object, *, tenant_id: str, mounted: object
    ) -> object:
        from korchestrator.models.tool import ToolResult

        self.calls.append((tool, dict(args)))  # type: ignore[arg-type]
        if not self._ok:
            return ToolResult(tool=tool, ok=False, error_code="TOOL_EXECUTION_FAILED", error="boom")
        return ToolResult(tool=tool, ok=True, output=self._output)

    def describe_tool(self, tool: str) -> str:
        return f"{tool}: a test tool"


async def test_an_agent_with_no_tools_never_touches_the_tool_invoker() -> None:
    pytest.importorskip("dspy")
    invoker = _FakeInvoker()
    agent = WorkerAgent(id="w", role="analyst").bind(
        clock=_clock(), gateway=MockLM(), tool_invoker=invoker
    )
    await agent.think(_state())
    assert invoker.calls == []


async def test_tools_declared_with_no_bound_invoker_raises_configuration_error() -> None:
    pytest.importorskip("dspy")
    agent = WorkerAgent(id="w", role="analyst", tools=("search",)).bind(
        clock=_clock(), gateway=MockLM()
    )
    with pytest.raises(ConfigurationError) as info:
        await agent.think(_state())
    assert "search" in str(info.value)


async def test_worker_calls_a_mounted_tool_then_answers() -> None:
    pytest.importorskip("dspy")
    gateway = _ScriptedGateway(
        [
            _react_reply(tool_name="search", tool_args='{"query": "incident"}', is_final=False),
            _react_reply(answer="found it", is_final=True),
        ]
    )
    invoker = _FakeInvoker(output="the incident report")
    agent = WorkerAgent(id="w", role="analyst", model="m1", tools=("search",)).bind(
        clock=_clock(), gateway=gateway, tool_invoker=invoker
    )
    update = await agent.think(_state())

    assert invoker.calls == [("search", {"query": "incident"})]
    assert [m.kind for m in update.messages] == ["tool", "answer"]
    assert "the incident report" in update.messages[0].content
    assert update.messages[1].content == "found it"
    assert update.halt is True


async def test_worker_stops_after_max_react_steps_without_a_final_answer() -> None:
    pytest.importorskip("dspy")
    # Every step calls the tool again and never answers; bounded by max_react_steps=2.
    step = _react_reply(tool_name="search", tool_args="{}", is_final=False)
    gateway = _ScriptedGateway([step, step, step, step])
    invoker = _FakeInvoker()
    agent = WorkerAgent(
        id="w", role="analyst", model="m1", tools=("search",), max_react_steps=2
    ).bind(clock=_clock(), gateway=gateway, tool_invoker=invoker)
    update = await agent.think(_state())

    assert len(invoker.calls) == 2  # bounded, not unbounded
    assert update.halt is False  # never reached is_final=True
    assert [m.kind for m in update.messages] == ["tool", "tool", "answer"]


async def test_invalid_tool_args_json_becomes_an_error_observation_not_a_crash() -> None:
    pytest.importorskip("dspy")
    gateway = _ScriptedGateway(
        [
            _react_reply(tool_name="search", tool_args="not json", is_final=False),
            _react_reply(answer="gave up", is_final=True),
        ]
    )
    invoker = _FakeInvoker()
    agent = WorkerAgent(id="w", role="analyst", model="m1", tools=("search",)).bind(
        clock=_clock(), gateway=gateway, tool_invoker=invoker
    )
    update = await agent.think(_state())

    assert invoker.calls == []  # the malformed call never reached the invoker
    assert "not a valid JSON object" in update.messages[0].content
    assert update.messages[1].content == "gave up"


async def test_a_failing_tool_result_is_fed_back_as_an_observation() -> None:
    pytest.importorskip("dspy")
    gateway = _ScriptedGateway(
        [
            _react_reply(tool_name="search", tool_args="{}", is_final=False),
            _react_reply(answer="handled the failure", is_final=True),
        ]
    )
    invoker = _FakeInvoker(ok=False)
    agent = WorkerAgent(id="w", role="analyst", model="m1", tools=("search",)).bind(
        clock=_clock(), gateway=gateway, tool_invoker=invoker
    )
    update = await agent.think(_state())

    assert "failed" in update.messages[0].content
    assert update.messages[1].content == "handled the failure"
