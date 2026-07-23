"""Integration: an MCP server's tool reaches a real agent through a full swarm run (spec 12 P10.2).

``MCPClient.discover`` (unit-tested in ``tests/unit/mcp/``) turns a fake MCP session's advertised
tools into :class:`~korchestrator.interfaces.Connector` objects; the ReAct loop (unit-tested in
``tests/unit/agents/test_worker.py``) drives a mounted tool. This file's job is to prove the two
wire together end to end: ``MCPClient.discover(...)`` -> ``Swarm(connectors=[...])`` ->
``ConnectorRegistry`` -> ``RegistryToolInvoker`` -> ``WorkerAgent``'s ReAct loop -> the fake MCP
session's ``call_tool``, and the result reaching ``RunResult.final_answer``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

pytest.importorskip("dspy")

from korchestrator import Swarm
from korchestrator.agents import WorkerAgent
from korchestrator.mcp import MCPClient, MCPServerConfig
from korchestrator.mcp.session import MCPCallResult, MCPToolSpec
from korchestrator.models.state import Message, MessageRole, RunStatus

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _react_reply(
    *, tool_name: str = "", tool_args: str = "", answer: str = "", is_final: bool
) -> str:
    """Build a dspy chat-adapter-formatted ``ReActWorkerSignature`` reply."""
    return (
        "[[ ## thought ## ]]\nreasoning\n\n"
        f"[[ ## tool_name ## ]]\n{tool_name}\n\n"
        f"[[ ## tool_args ## ]]\n{tool_args}\n\n"
        f"[[ ## answer ## ]]\n{answer}\n\n"
        f"[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"
    )


class _ScriptedGateway:
    """A gateway returning one scripted reply per call, in order."""

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


class _FakeMCPSession:
    """A deterministic, offline stand-in for a real ``mcp`` transport session (T1)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self) -> list[MCPToolSpec]:
        return [MCPToolSpec(name="weather", description="look up today's weather for a city")]

    async def call_tool(self, name: str, args: dict[str, object]) -> MCPCallResult:
        self.calls.append((name, args))
        return MCPCallResult(output=f"sunny in {args.get('city')}")

    async def aclose(self) -> None:
        pass


def test_a_worker_calls_a_discovered_mcp_tool_through_a_full_swarm_run() -> None:
    session = _FakeMCPSession()

    async def factory(config: MCPServerConfig) -> _FakeMCPSession:
        return session

    client = MCPClient(session_factory=factory)
    connectors = asyncio.run(
        client.discover(MCPServerConfig(name="weather-server", transport="stdio", command="x"))
    )

    gateway = _ScriptedGateway(
        [
            _react_reply(tool_name="weather", tool_args='{"city": "Austin"}', is_final=False),
            _react_reply(answer="sunny in Austin", is_final=True),
        ]
    )
    swarm = Swarm(
        objective="Look up today's weather in Austin",
        model_gateway=gateway,
        connectors=connectors,
    ).add(WorkerAgent(id="forecaster", role="forecaster", model="m1", tools=("weather",)))

    result = swarm.run()

    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == "sunny in Austin"
    assert session.calls == [("weather", {"city": "Austin"})]
    tool_messages = [m for m in result.messages if m.kind == "tool"]
    assert len(tool_messages) == 1
    assert "sunny in Austin" in tool_messages[0].content


def test_an_mcp_server_that_fails_to_connect_contributes_no_tools_and_the_run_still_completes() -> (
    None
):
    async def failing_factory(config: MCPServerConfig) -> _FakeMCPSession:
        raise ConnectionRefusedError("server unreachable")

    client = MCPClient(session_factory=failing_factory)
    connectors = asyncio.run(
        client.discover(MCPServerConfig(name="down-server", transport="stdio", command="x"))
    )
    assert connectors == []

    gateway = _ScriptedGateway([_react_reply(answer="no tools available", is_final=True)])
    swarm = Swarm(
        objective="Try to use a tool from a server that is down",
        model_gateway=gateway,
        connectors=connectors,
    ).add(WorkerAgent(id="w", role="w", model="m1"))

    result = swarm.run()

    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == "no tools available"
