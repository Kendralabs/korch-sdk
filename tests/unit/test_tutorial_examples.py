"""Locks the runnable code shown in docs/tutorials/*.md against future API drift (P11.3).

Each test mirrors one tutorial's exact snippet. A change that breaks a documented example fails
here, not in front of a reader following the docs.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from korchestrator import Agent, Swarm
from korchestrator.interfaces import BaseRouter
from korchestrator.models.routing import RoutingContext, RoutingResult
from korchestrator.models.state import AgentState, Message, MessageRole, RunStatus, StateUpdate
from korchestrator.providers import MockLM
from korchestrator.routing import UserFunctionRouter
from korchestrator.tools import ConnectorRegistry

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# --- tutorials/swarm.md ---------------------------------------------------------------------------


def test_swarm_tutorial_topology_and_trace() -> None:
    pytest.importorskip("dspy")
    gateway = MockLM(
        responses={
            "gpt-4o-mini": "No obvious security issues found.",
            "claude-3.5-haiku": "Performance looks acceptable; no hot loops detected.",
        }
    )
    swarm = (
        Swarm(objective="Review this change for security and performance", model_gateway=gateway)
        .add(Agent(id="security", role="security-reviewer", model="gpt-4o-mini"))
        .add(Agent(id="perf", role="performance-reviewer", model="claude-3.5-haiku"))
        .add(Agent(id="lead", role="review-lead"))
        .edges([("security", "lead"), ("perf", "lead")])
    )
    result = swarm.run(max_supersteps=5)
    assert result.status is RunStatus.COMPLETED
    assert result.supersteps == 2
    senders_by_superstep = {(m.superstep, m.sender) for m in result.messages}
    assert (0, "lead") in senders_by_superstep
    assert (1, "lead") in senders_by_superstep


# --- tutorials/custom-agent.md ----------------------------------------------------------------


class WordCountAgent(Agent):
    """The tutorial's minimal custom agent — no DSPy, no model gateway."""

    async def think(self, state: AgentState) -> StateUpdate:
        total = len(state.objective.split())
        message = Message(
            id=f"{state.run_id}:{state.superstep}:{self.id}:0",
            role=MessageRole.ASSISTANT,
            kind="answer",
            sender=self.id,
            content=f"{total} words",
            superstep=state.superstep,
            valid_time=self.clock.now(),
        )
        return StateUpdate(
            agent_id=self.id, messages=(message,), halt=True, valid_time=message.valid_time
        )


def test_custom_agent_tutorial_standalone() -> None:
    swarm = Swarm(objective="Count the words in this objective").add(
        WordCountAgent(id="counter", role="counter")
    )
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == "6 words"


class ThoughtWordCountAgent(Agent):
    """The tutorial's variant mixed with a default agent (kind="thought", not "answer")."""

    async def think(self, state: AgentState) -> StateUpdate:
        total = len(state.objective.split())
        message = Message(
            id=f"{state.run_id}:{state.superstep}:{self.id}:0",
            role=MessageRole.ASSISTANT,
            kind="thought",
            sender=self.id,
            content=f"word count: {total}",
            superstep=state.superstep,
            valid_time=self.clock.now(),
        )
        return StateUpdate(
            agent_id=self.id, messages=(message,), halt=True, valid_time=message.valid_time
        )


def test_custom_agent_tutorial_mixed_with_default() -> None:
    pytest.importorskip("dspy")
    swarm = (
        Swarm(objective="Count words, then have a lead review the count", model_gateway=MockLM())
        .add(ThoughtWordCountAgent(id="counter", role="counter"))
        .add(Agent(id="lead", role="review-lead"))
        .edges([("counter", "lead")])
    )
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED
    assert [m.kind for m in result.messages] == ["thought", "answer", "answer"]


# --- tutorials/custom-tool.md -------------------------------------------------------------------


async def _convert_temperature(args: dict) -> str:
    celsius = float(args["celsius"])
    return f"{celsius}C is {celsius * 9 / 5 + 32}F"


def _react_reply(
    *, tool_name: str = "", tool_args: str = "", answer: str = "", is_final: bool
) -> str:
    return (
        "[[ ## thought ## ]]\nreasoning\n\n"
        f"[[ ## tool_name ## ]]\n{tool_name}\n\n"
        f"[[ ## tool_args ## ]]\n{tool_args}\n\n"
        f"[[ ## answer ## ]]\n{answer}\n\n"
        f"[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"
    )


class _ScriptedGateway:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    async def complete(
        self, messages: object, *, model: str, max_tokens: int | None = None
    ) -> Message:
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


def test_custom_tool_tutorial_calls_through_the_react_loop() -> None:
    pytest.importorskip("dspy")
    from korchestrator.agents import WorkerAgent

    registry = ConnectorRegistry().register_tool(
        "convert_temperature",
        {"type": "object", "properties": {"celsius": {"type": "number"}}, "required": ["celsius"]},
        _convert_temperature,
        description="Convert a Celsius temperature to Fahrenheit.",
    )
    gateway = _ScriptedGateway(
        [
            _react_reply(
                tool_name="convert_temperature", tool_args='{"celsius": 100}', is_final=False
            ),
            _react_reply(answer="100C is 212F", is_final=True),
        ]
    )
    swarm = Swarm(
        objective="Convert 100 degrees Celsius to Fahrenheit",
        model_gateway=gateway,
        connectors=registry,
    ).add(WorkerAgent(id="converter", role="converter", model="m1", tools=("convert_temperature",)))

    result = swarm.run()

    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == "100C is 212F"
    tool_messages = [m for m in result.messages if m.kind == "tool"]
    assert "convert_temperature" in tool_messages[0].content


# --- tutorials/mcp.md -----------------------------------------------------------------------------


def test_mcp_tutorial_fake_session_discovery() -> None:
    import asyncio

    from korchestrator.mcp import MCPClient, MCPServerConfig
    from korchestrator.mcp.session import MCPCallResult, MCPToolSpec

    class FakeMCPSession:
        async def list_tools(self) -> list[MCPToolSpec]:
            return [MCPToolSpec(name="weather", description="look up today's weather for a city")]

        async def call_tool(self, name: str, args: dict) -> MCPCallResult:
            return MCPCallResult(output=f"sunny in {args['city']}")

        async def aclose(self) -> None:
            pass

    async def factory(config: object) -> FakeMCPSession:
        return FakeMCPSession()

    client = MCPClient(session_factory=factory)
    connectors = asyncio.run(
        client.discover(MCPServerConfig(name="weather-server", transport="stdio", command="x"))
    )
    assert [c.name for c in connectors] == ["weather"]


# --- tutorials/custom-router.md ---------------------------------------------------------------


def test_custom_router_tutorial_pin_to_cheapest() -> None:
    pytest.importorskip("dspy")

    def pin_to_cheapest(context: RoutingContext) -> RoutingResult:
        return RoutingResult(
            model_name="gpt-4o-mini",
            strategy="user_function",
            score=1.0,
            reason="pinned to the cheapest available model for every agent",
        )

    gateway = MockLM()
    swarm = Swarm(
        objective="Summarize the incident report clearly",
        model_gateway=gateway,
        router=UserFunctionRouter(pin_to_cheapest),
    ).add(Agent(id="analyst", role="analyst"))
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED
    assert {call.model for call in gateway.calls} == {"gpt-4o-mini"}


def test_custom_router_tutorial_route_by_difficulty() -> None:
    pytest.importorskip("dspy")

    def route_by_difficulty(context: RoutingContext) -> RoutingResult:
        model = "gpt-4o-mini" if context.task.difficulty == "trivial" else "gpt-4o"
        return RoutingResult(
            model_name=model,
            strategy="user_function",
            score=1.0,
            reason=f"{context.task.difficulty} task routed to {model}",
        )

    gateway = MockLM()
    swarm = Swarm(
        objective="Summarize the incident report clearly",
        model_gateway=gateway,
        router=UserFunctionRouter(route_by_difficulty),
    ).add(Agent(id="analyst", role="analyst"))
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED
    assert {call.model for call in gateway.calls} == {"gpt-4o"}


def test_custom_router_tutorial_full_base_router_subclass() -> None:
    pytest.importorskip("dspy")

    class MyRouter(BaseRouter):
        def __init__(self, default_model: str) -> None:
            self._default_model = default_model

        async def select_model(self, context: RoutingContext) -> RoutingResult:
            return RoutingResult(
                model_name=self._default_model,
                strategy="user_function",
                score=1.0,
                reason="always routes to the configured default",
            )

    gateway = MockLM()
    swarm = Swarm(
        objective="Summarize the incident report clearly",
        model_gateway=gateway,
        router=MyRouter("gpt-4o-mini"),
    ).add(Agent(id="analyst", role="analyst"))
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED
    assert {call.model for call in gateway.calls} == {"gpt-4o-mini"}


# --- tutorials/streaming.md -----------------------------------------------------------------------


def test_streaming_tutorial_drain_and_format_sse() -> None:
    pytest.importorskip("dspy")
    import asyncio

    from korchestrator.events import Event, EventPublisher, format_sse

    publisher = EventPublisher()
    subscription = publisher.subscribe()

    async def on_superstep(event: Event) -> None:
        await publisher.publish(event)

    swarm = (
        Swarm(objective="Review this change for security and performance", model_gateway=MockLM())
        .add(Agent(id="security", role="security-reviewer"))
        .add(Agent(id="perf", role="performance-reviewer"))
        .add(Agent(id="lead", role="review-lead"))
        .edges([("security", "lead"), ("perf", "lead")])
        .on("superstep", on_superstep)
    )
    result = swarm.run(max_supersteps=5)
    assert result.status is RunStatus.COMPLETED

    async def drain(count: int) -> list[Event]:
        return [await subscription.get() for _ in range(count)]

    events = asyncio.run(drain(result.supersteps))
    subscription.close()

    assert [e.payload["superstep"] for e in events] == list(range(1, result.supersteps + 1))
    assert all(e.payload["status"] == "running" for e in events)
    frames = [format_sse(e) for e in events]
    assert all(frame.startswith("event: superstep\ndata: {") for frame in frames)
