"""Unit tests for the unified Agent base (spec 06 §5, spec 07 §4, ADR 0012, P4.4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import korchestrator
from fixtures.fake_clock import FakeClock
from korchestrator.agents import Agent
from korchestrator.core.graph import Node
from korchestrator.exceptions import ConfigurationError, ValidationError
from korchestrator.models.state import AgentState, Message, MessageRole, StateUpdate

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _state(objective: str = "Count the words in this objective", superstep: int = 0) -> AgentState:
    return AgentState(
        run_id="run-1", objective=objective, superstep=superstep, transaction_time=NOW
    )


class WordCountAgent(Agent):
    """A fully custom agent that answers with the objective's word count (mirrors spec 07 §4)."""

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


def test_one_agent_class_reachable_from_every_documented_path() -> None:
    # Unified: top-level, cognitive layer, and façade all resolve to the same class (ADR 0012).
    assert korchestrator.Agent is Agent
    assert korchestrator.services.Agent is Agent


def test_declarative_construction_exposes_config() -> None:
    agent = Agent(id="lead", role="review-lead", model="gpt-4o")
    assert agent.id == "lead"
    assert agent.persona.role == "review-lead"
    assert agent.config.model == "gpt-4o"


def test_invalid_id_raises_korch_validation_error_not_pydantic() -> None:
    with pytest.raises(ValidationError):
        Agent(id="Not Valid!", role="x")


def test_clock_is_required_before_use() -> None:
    with pytest.raises(ConfigurationError):
        _ = Agent(id="a", role="r").clock


def test_bind_injects_the_clock_and_chains() -> None:
    agent = Agent(id="a", role="r")
    returned = agent.bind(clock=FakeClock(start=NOW))
    assert returned is agent  # chaining
    assert agent.clock.now() == NOW


def test_to_node_binds_config_and_think() -> None:
    agent = WordCountAgent(id="counter", role="counter")
    node = agent.to_node()
    assert isinstance(node, Node)
    assert node.id == "counter"
    assert node.compute == agent.think


def test_is_complete_defaults_to_false() -> None:
    assert Agent(id="a", role="r").is_complete(_state()) is False


async def test_base_think_raises_until_overridden_or_wired() -> None:
    with pytest.raises(NotImplementedError):
        await Agent(id="a", role="r").bind(clock=FakeClock()).think(_state())


async def test_custom_agent_runs_against_a_frozen_snapshot() -> None:
    agent = WordCountAgent(id="counter", role="counter").bind(clock=FakeClock(start=NOW))
    update = await agent.think(_state("Count the words in this objective"))
    assert update.agent_id == "counter"
    assert update.halt is True
    assert update.messages[0].content == "6 words"
    assert update.messages[0].valid_time == NOW


def test_agent_state_snapshot_is_immutable() -> None:
    # The frozen-snapshot rule is enforced by the model: think cannot mutate what it is given.
    state = _state()
    with pytest.raises(Exception):  # noqa: B017 — pydantic raises on any frozen-field assignment
        state.superstep = 5  # type: ignore[misc]
