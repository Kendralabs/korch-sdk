"""Integration: a real agent calls a real tool through a full swarm run (spec 12 P10.2).

Every piece here is separately unit-tested (the AUB bridge in ``tests/unit/tools/``, the ReAct
loop in ``tests/unit/agents/test_worker.py``, the router strategies in ``tests/unit/routing/``) —
this file's job is to prove the pieces are actually wired together end to end: `Swarm(connectors=
[...])` -> `ConnectorRegistry` -> `RegistryToolInvoker` -> `WorkerAgent`'s ReAct loop -> a real
`FilesystemConnector`, and the result reaching `RunResult.final_answer`. This gap (the AUB bridge
and the agent reasoning loop were never connected) is exactly what writing this test surfaced —
see ADR 0018 and the P10.2 engineering-log entry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("dspy")

from korchestrator import Swarm
from korchestrator.agents import WorkerAgent
from korchestrator.models.state import Message, MessageRole, RunStatus
from korchestrator.tools import FilesystemConnector

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


def test_a_worker_reads_a_real_file_through_the_filesystem_connector(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("the answer is 42", encoding="utf-8")
    gateway = _ScriptedGateway(
        [
            _react_reply(tool_name="read_file", tool_args='{"path": "note.txt"}', is_final=False),
            _react_reply(answer="the answer is 42", is_final=True),
        ]
    )
    swarm = Swarm(
        objective="Read note.txt and report exactly what it says",
        model_gateway=gateway,
        connectors=[FilesystemConnector(tmp_path)],
    ).add(WorkerAgent(id="reader", role="reader", model="m1", tools=("read_file",)))

    result = swarm.run()

    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == "the answer is 42"
    tool_messages = [m for m in result.messages if m.kind == "tool"]
    assert len(tool_messages) == 1
    assert "note.txt" in tool_messages[0].content


def test_a_tool_outside_the_mount_gate_never_reaches_the_connector(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
    # The agent mounts a *different* tool; the model still tries "read_file", and the AUB access
    # gate denies it before the connector ever runs — the ReAct loop sees the denial as an
    # ordinary observation and can still answer, it just never learns the file's contents.
    gateway = _ScriptedGateway(
        [
            _react_reply(tool_name="read_file", tool_args='{"path": "secret.txt"}', is_final=False),
            _react_reply(answer="access was denied", is_final=True),
        ]
    )
    swarm = Swarm(
        objective="Try to read a file you were not given access to",
        model_gateway=gateway,
        connectors=[FilesystemConnector(tmp_path)],
    ).add(WorkerAgent(id="reader", role="reader", model="m1", tools=("other_tool",)))

    result = swarm.run()

    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == "access was denied"
    tool_messages = [m for m in result.messages if m.kind == "tool"]
    assert (
        "denied" in tool_messages[0].content.lower()
        or "not mounted" in tool_messages[0].content.lower()
    )
