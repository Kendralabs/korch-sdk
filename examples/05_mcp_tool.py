"""Discovering and mounting an MCP server's tools — offline, via a fake session.

A real server would use MCPClient() with no session_factory=, speaking the real [mcp] transport;
the fake session here exercises the exact same discovery -> mount -> call path without needing a
real server process running.

Run: python examples/05_mcp_tool.py
Requires: pip install "korchestrator[dspy,mcp]"
"""

import asyncio
from datetime import datetime, timezone

from korchestrator import Swarm
from korchestrator.agents import WorkerAgent
from korchestrator.mcp import MCPClient, MCPServerConfig
from korchestrator.mcp.session import MCPCallResult, MCPToolSpec
from korchestrator.models.state import Message, MessageRole

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeMCPSession:
    """A stand-in for a real MCP transport session."""

    async def list_tools(self):
        return [MCPToolSpec(name="weather", description="look up today's weather for a city")]

    async def call_tool(self, name, args):
        return MCPCallResult(output=f"sunny in {args['city']}")

    async def aclose(self):
        pass


async def factory(config):
    return FakeMCPSession()


def react_reply(*, tool_name="", tool_args="", answer="", is_final=False):
    return (
        "[[ ## thought ## ]]\nreasoning\n\n"
        f"[[ ## tool_name ## ]]\n{tool_name}\n\n"
        f"[[ ## tool_args ## ]]\n{tool_args}\n\n"
        f"[[ ## answer ## ]]\n{answer}\n\n"
        f"[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"
    )


class ScriptedGateway:
    def __init__(self, replies):
        self._replies = list(replies)

    async def complete(self, messages, *, model, max_tokens=None):
        content = self._replies.pop(0) if self._replies else ""
        return Message(
            id="m",
            role=MessageRole.ASSISTANT,
            sender="mock",
            content=content,
            superstep=0,
            valid_time=NOW,
        )

    async def available_models(self):
        return []


client = MCPClient(session_factory=factory)
server = MCPServerConfig(name="weather-server", transport="stdio", command="weather-mcp")
connectors = asyncio.run(client.discover(server))
print("discovered tools:", [c.name for c in connectors])

gateway = ScriptedGateway(
    [
        react_reply(tool_name="weather", tool_args='{"city": "Austin"}', is_final=False),
        react_reply(answer="sunny in Austin", is_final=True),
    ]
)
swarm = Swarm(
    objective="Look up today's weather in Austin",
    model_gateway=gateway,
    connectors=connectors,
).add(WorkerAgent(id="forecaster", role="forecaster", model="m1", tools=("weather",)))

result = swarm.run()

print("status:", result.status)
print("final_answer:", result.final_answer)
assert result.final_answer == "sunny in Austin"
