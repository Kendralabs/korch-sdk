"""Regression: PregelRunner's message log used to silently drop every non-answer message.

**Issue.** `PregelRunner._route_messages` accumulated only `kind == "answer"` messages into
`AgentState.messages` / `RunResult.messages`; every `"thought"`/`"tool"`/`"handoff"` message was
routed to inboxes but never reached the log. Invisible until P10.2 (ADR 0018), because until then
every `StateUpdate` in the codebase carried exactly one message, always `kind="answer"`. Once
`WorkerAgent`'s ReAct loop started emitting a `"tool"` message ahead of its `"answer"` in the same
`StateUpdate`, `tests/integration/test_tools_integration.py` caught it: the run completed with the
correct `final_answer`, but `result.messages` had zero `"tool"`-kind entries.

**Fix.** `PregelRunner._route_messages` (`src/korchestrator/core/pregel.py`) now accumulates every
message regardless of `kind` into the log; `build_result`'s `final_answer` is unaffected, since it
already filters the log down to `kind == "answer"` before joining. See the P10.2 engineering-log
entry and ADR 0018 for the full account.

This test locks the kernel-level behavior directly (no DSPy, no agent — just `PregelRunner` and a
synthetic node), so it fails immediately if the log ever narrows back to answer-only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.core import PregelRunner
from korchestrator.core.graph import AgentGraph, Node
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, Message, StateUpdate

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _msg(content: str, *, kind: str) -> Message:
    return Message(
        id="placeholder",
        sender="placeholder",
        content=content,
        kind=kind,
        superstep=0,
        valid_time=NOW,
    )


async def _reasoner(state: AgentState) -> StateUpdate:
    # One turn, three message kinds — exactly the shape a ReAct step produces (P10.2): one or more
    # "tool" observations, then a final "answer", all in a single StateUpdate.
    return StateUpdate(
        agent_id="worker",
        messages=(
            _msg("thinking it over", kind="thought"),
            _msg("tool search(...) -> 3 results", kind="tool"),
            _msg("the answer is 42", kind="answer"),
        ),
        halt=True,
        valid_time=NOW,
    )


async def test_the_message_log_keeps_every_kind_not_just_answers() -> None:
    node = Node(AgentConfig(id="worker", persona=AgentPersona(role="r")), _reasoner)
    runner = PregelRunner(AgentGraph([node]), clock=lambda: NOW)
    start = AgentState(run_id="r1", objective="answer the question directly", transaction_time=NOW)

    result = await runner.run(start)

    kinds = [message.kind for message in result.messages]
    assert kinds == ["thought", "tool", "answer"]
    # final_answer still correctly narrows to just the answer-kind content.
    assert result.final_answer == "the answer is 42"
