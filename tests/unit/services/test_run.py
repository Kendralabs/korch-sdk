"""End-to-end façade tests: Korch.run and Swarm.run against the kernel (spec 04, P4.9)."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from korchestrator import Agent, Korch, Swarm
from korchestrator.exceptions import MissingExtraError, ValidationError
from korchestrator.models.state import AgentState, Message, MessageRole, RunStatus, StateUpdate
from korchestrator.providers import MockLM


class WordCountAgent(Agent):
    """A custom agent (own ``think``, no dspy) that answers with the objective's word count."""

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


# --- guards (no dspy) ---------------------------------------------------------------------------


def test_korch_rejects_a_short_objective() -> None:
    with pytest.raises(ValidationError):
        Korch().run("too short")


def test_swarm_rejects_a_short_objective() -> None:
    with pytest.raises(ValidationError):
        Swarm(objective="too short").add(Agent(id="a", role="a")).run()


def test_korch_reasoning_without_dspy_raises_missing_extra() -> None:
    with mock.patch.dict(sys.modules, {"dspy": None}), pytest.raises(MissingExtraError):
        Korch().run("Summarize the quarterly incident reports")


# --- custom agents run on a base install (no dspy) ----------------------------------------------


def test_custom_agent_swarm_runs_end_to_end_without_dspy() -> None:
    # A custom agent supplies its own reasoning, so the full path runs with no [dspy] extra
    # (spec 11 §137) and is deterministic.
    swarm = Swarm(objective="Count the words in this objective").add(
        WordCountAgent(id="counter", role="counter")
    )
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == "6 words"


# --- reasoning path (dspy + MockLM) -------------------------------------------------------------


def test_korch_run_completes_with_an_answer() -> None:
    pytest.importorskip("dspy")
    result = Korch(model_gateway=MockLM()).run("Summarize the quarterly incident reports clearly")
    assert result.status is RunStatus.COMPLETED
    assert result.final_answer


def test_swarm_run_honours_the_declared_topology() -> None:
    pytest.importorskip("dspy")
    swarm = (
        Swarm(objective="Review this change for security and performance", model_gateway=MockLM())
        .add(Agent(id="security", role="security-reviewer"))
        .add(Agent(id="perf", role="performance-reviewer"))
        .add(Agent(id="lead", role="review-lead"))
        .edges([("security", "lead"), ("perf", "lead")])
    )
    result = swarm.run(max_supersteps=5)
    assert result.status is RunStatus.COMPLETED
    assert result.final_answer
    # The lead runs after receiving the reviewers' messages, so all three contribute.
    assert {"security", "perf", "lead"} <= {message.sender for message in result.messages}
