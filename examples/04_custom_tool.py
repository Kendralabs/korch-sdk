"""A custom tool, mounted and called through the bounded ReAct loop.

Run: python examples/04_custom_tool.py
Requires: pip install "korchestrator[dspy]"
"""

from datetime import datetime, timezone

from korchestrator import Swarm
from korchestrator.agents import WorkerAgent
from korchestrator.models.state import Message, MessageRole
from korchestrator.tools import ConnectorRegistry

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def convert_temperature(args: dict) -> str:
    celsius = float(args["celsius"])
    return f"{celsius}C is {celsius * 9 / 5 + 32}F"


registry = ConnectorRegistry().register_tool(
    "convert_temperature",
    {"type": "object", "properties": {"celsius": {"type": "number"}}, "required": ["celsius"]},
    convert_temperature,
    description="Convert a Celsius temperature to Fahrenheit.",
)


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
            id="m",
            role=MessageRole.ASSISTANT,
            sender="mock",
            content=content,
            superstep=0,
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

print("status:", result.status)
print("final_answer:", result.final_answer)
tool_messages = [m for m in result.messages if m.kind == "tool"]
print("tool call:", tool_messages[0].content)

assert result.final_answer == "100C is 212F"
