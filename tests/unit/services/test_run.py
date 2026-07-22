"""End-to-end façade tests: Korch.run and Swarm.run against the kernel (spec 04, P4.9)."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from korchestrator import Agent, Korch, Swarm
from korchestrator.exceptions import MissingExtraError, ValidationError
from korchestrator.models.routing import RoutingContext, RoutingResult
from korchestrator.models.state import AgentState, Message, MessageRole, RunStatus, StateUpdate
from korchestrator.providers import MockLM
from korchestrator.routing import UserFunctionRouter


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


# --- routing wiring (P5.6) ----------------------------------------------------------------------


def test_custom_router_influences_the_run() -> None:
    pytest.importorskip("dspy")
    # A custom router pins every agent to one model; the choice must reach the gateway.
    seen: list[str] = []

    def pin(context: RoutingContext) -> RoutingResult:
        seen.append(context.agent_id)
        return RoutingResult(
            model_name="pinned-model", strategy="user_function", score=1.0, reason="test pin"
        )

    gateway = MockLM()
    swarm = Swarm(
        objective="Summarize the incident report clearly",
        model_gateway=gateway,
        router=UserFunctionRouter(pin),
    ).add(Agent(id="w", role="analyst"))
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED
    assert seen == ["w"]  # the router was consulted for the declared agent
    assert "pinned-model" in {call.model for call in gateway.calls}


def test_agent_model_map_reaches_the_gateway() -> None:
    pytest.importorskip("dspy")
    from korchestrator.config import Settings

    gateway = MockLM()
    swarm = Swarm(
        objective="Summarize the incident report clearly",
        settings=Settings(agent_model_map={"w": "gpt-4o"}),
        model_gateway=gateway,
    ).add(Agent(id="w", role="analyst"))
    swarm.run()
    assert "gpt-4o" in {call.model for call in gateway.calls}


# --- middleware / hooks (P6.8) ------------------------------------------------------------------


def test_hooks_fire_around_supersteps_and_a_raising_hook_is_isolated() -> None:
    # No dspy needed: WordCountAgent supplies its own reasoning. A raising middleware must not fail
    # the run, and the superstep event hook must still fire (spec 07 §9).
    from korchestrator.services import Middleware

    events_seen: list[str] = []

    class Boom(Middleware):
        async def before_superstep(self, state: object) -> None:
            raise RuntimeError("hook exploded")

    swarm = Swarm(objective="Count the words in this objective", middleware=[Boom()]).add(
        WordCountAgent(id="counter", role="counter")
    )
    swarm.on("superstep", lambda event: events_seen.append(event.name))
    result = swarm.run()
    assert result.status is RunStatus.COMPLETED  # the raising middleware was isolated
    assert result.final_answer == "6 words"
    assert "superstep" in events_seen  # the event hook still fired
