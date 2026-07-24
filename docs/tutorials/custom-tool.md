# Writing a custom tool

Tools give agents something to *call*, not just something to say. This tutorial mounts a bare
function as a tool on a `WorkerAgent` and drives it through a scripted reasoning loop so the whole
path — model decides to call the tool, the tool runs, the result comes back — is visible end to
end and runs with no network and no real model.

## Register a function as a tool

The simplest path is `ConnectorRegistry.register_tool(name, schema, function)` — no class to write:

```python
from korchestrator.tools import ConnectorRegistry


async def convert_temperature(args: dict) -> str:
    celsius = float(args["celsius"])
    return f"{celsius}C is {celsius * 9 / 5 + 32}F"


registry = ConnectorRegistry().register_tool(
    "convert_temperature",
    {"type": "object", "properties": {"celsius": {"type": "number"}}, "required": ["celsius"]},
    convert_temperature,
    description="Convert a Celsius temperature to Fahrenheit.",
)
```

The `schema` is standard JSON Schema — the Agent Utility Bridge validates every call's arguments
against it before your function ever runs, so `convert_temperature` never has to check that
`"celsius"` is present and numeric itself.

## Mount it on an agent

Pass the registry to `Swarm`/`Korch` via `connectors=`, and name the tool in the agent's `tools=`:

```python
from korchestrator import Swarm
from korchestrator.agents import WorkerAgent
from korchestrator.providers import MockLM

swarm = Swarm(
    objective="Convert 100 degrees Celsius to Fahrenheit",
    model_gateway=MockLM(),
    connectors=registry,
).add(WorkerAgent(id="converter", role="converter", tools=("convert_temperature",)))
```

An agent whose `tools` names something the swarm has no `connectors=` for raises a
`ConfigurationError` naming the missing tool — you find out at construction time, not mid-run.

Mounting a tool switches that agent from a single reasoning pass to a **bounded ReAct loop**: each
step lets the model either call one mounted tool or answer, up to `max_react_steps` (default 3).
Every tool call becomes its own `kind="tool"` message in `result.messages`, ahead of the final
`kind="answer"`.

## Seeing it call the tool

`MockLM`'s default echo doesn't decide to call tools — it just echoes the prompt. To see a real
tool call happen, script a gateway that plays the model's two turns: first deciding to call
`convert_temperature`, then answering from the result.

```python
from datetime import datetime, timezone

from korchestrator.models.state import Message, MessageRole

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def react_reply(*, tool_name="", tool_args="", answer="", is_final=False):
    """Build a reply in the format the ReAct loop's signature expects."""
    return (
        "[[ ## thought ## ]]\nreasoning\n\n"
        f"[[ ## tool_name ## ]]\n{tool_name}\n\n"
        f"[[ ## tool_args ## ]]\n{tool_args}\n\n"
        f"[[ ## answer ## ]]\n{answer}\n\n"
        f"[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"
    )


class ScriptedGateway:
    """Plays back one scripted reply per call, in order — a stand-in for a real model's turns."""

    def __init__(self, replies):
        self._replies = list(replies)

    async def complete(self, messages, *, model, max_tokens=None):
        content = self._replies.pop(0) if self._replies else ""
        return Message(
            id="m", role=MessageRole.ASSISTANT, sender="mock", content=content, superstep=0,
            valid_time=NOW,
        )

    async def available_models(self):
        return []


gateway = ScriptedGateway(
    [
        react_reply(tool_name="convert_temperature", tool_args='{"celsius": 100}', is_final=False),
        react_reply(answer="100C is 212F", is_final=True),
    ]
)

swarm = Swarm(
    objective="Convert 100 degrees Celsius to Fahrenheit",
    model_gateway=gateway,
    connectors=registry,
).add(WorkerAgent(id="converter", role="converter", model="m1", tools=("convert_temperature",)))

result = swarm.run()
print(result.status, result.final_answer)
# RunStatus.COMPLETED 100C is 212F

tool_messages = [m for m in result.messages if m.kind == "tool"]
print(tool_messages[0].content)
# tool convert_temperature({'celsius': 100}) -> '100.0C is 212.0F'
```

## When you need more than a function

`register_tool` wraps your function so any exception becomes a generic failed `ToolResult`. If you
need to distinguish *expected* failures (e.g. "file not found" vs. "permission denied") with your
own error codes, implement the full `Connector` protocol instead (`name`, `description`, `schema`
properties plus an `async execute(tool, args, *, tenant_id) -> ToolResult` method) and register it
with `registry.register_connector(my_connector)`. `korchestrator.tools.FilesystemConnector` is a
worked example of this fuller shape in the SDK itself.

## Next

- [Connecting an MCP server](mcp.md) — mount tools from an external MCP server the same way.
- [Building a swarm](swarm.md) if you haven't yet — tools compose with any topology.
