# Connecting an MCP server

[Model Context Protocol](https://modelcontextprotocol.io) (MCP) servers expose tools over a
standard transport. `MCPClient.discover` turns a server's advertised tools into the same
`Connector` objects a native tool uses — an agent cannot tell an MCP tool from one you wrote
yourself with [`register_tool`](custom-tool.md).

## Requires the `[mcp]` extra

```bash
pip install "korchestrator[mcp]"
```

## Discover a server's tools

```python
import asyncio

from korchestrator.mcp import MCPClient, MCPServerConfig

client = MCPClient()  # uses the real [mcp] transport
connectors = asyncio.run(
    client.discover(
        MCPServerConfig(name="weather-server", transport="stdio", command="weather-mcp")
    )
)
print([connector.name for connector in connectors])
```

`transport="stdio"` spawns `command` as a subprocess and speaks MCP over its stdin/stdout;
`transport="sse"` connects to a `url` instead. A connection or discovery failure is logged and
skipped, never raised — the server simply contributes no tools, so mounting one of its tool names
on an agent resolves to `TOOL_NOT_FOUND` rather than crashing the run.

## Mount discovered tools on a swarm

Pass the discovered connectors straight to `connectors=`, exactly like a hand-written tool:

```python
from korchestrator import Swarm
from korchestrator.agents import WorkerAgent

swarm = Swarm(
    objective="Look up today's weather in Austin",
    connectors=connectors,
).add(WorkerAgent(id="forecaster", role="forecaster", tools=("weather",)))
```

## A runnable, offline version

You don't need a real MCP server to see this work: `MCPClient(session_factory=...)` accepts any
object satisfying the `list_tools`/`call_tool`/`aclose` shape, so a fake session exercises exactly
the same discovery → registration → mount path a real server would, offline and deterministically:

```python
from korchestrator.mcp.session import MCPCallResult, MCPToolSpec


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


client = MCPClient(session_factory=factory)
connectors = asyncio.run(
    client.discover(MCPServerConfig(name="weather-server", transport="stdio", command="weather-mcp"))
)
print([connector.name for connector in connectors])
# ['weather']
```

Feed the resulting `connectors` into `Swarm(connectors=connectors)` exactly as above and a
`WorkerAgent` with `tools=("weather",)` will call it through the same bounded ReAct loop described
in [Writing a custom tool](custom-tool.md) — that tutorial's scripted-gateway pattern applies here
unchanged, since the tool call site is identical regardless of whether the tool came from MCP or a
`register_tool` call.

## Next

- [Writing a custom tool](custom-tool.md) — the mount-and-call mechanics this tutorial builds on.
- [Human-in-the-loop](hitl.md) — pause a run before an agent acts on a tool's result.
