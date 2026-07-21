"""Contract tests for the P1 façade signatures (P1.5).

The façade surface is frozen here: builders collect topology; execution raises
``NotImplementedError`` until P4.9. These tests lock the current, deliberate behaviour.
"""

from __future__ import annotations

import pytest

from korchestrator import Agent, Korch, Swarm
from korchestrator.models.agent import AgentConfig


def test_agent_builds_an_immutable_config() -> None:
    agent = Agent(id="lead", role="review-lead")
    assert agent.id == "lead"
    assert isinstance(agent.config, AgentConfig)
    assert agent.config.persona.role == "review-lead"
    assert agent.config.model is None


def test_agent_carries_model_and_tools() -> None:
    agent = Agent(id="security", role="security-reviewer", model="gpt-4o-mini", tools=("grep",))
    assert agent.config.model == "gpt-4o-mini"
    assert agent.config.tools == ("grep",)


def test_agent_rejects_an_invalid_id() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Agent(id="Upper", role="r")


def test_swarm_builder_collects_agents_and_edges() -> None:
    swarm = (
        Swarm(objective="Review this PR for security and performance")
        .add(Agent(id="security", role="security-reviewer"))
        .add(Agent(id="lead", role="review-lead"))
        .edges([("security", "lead")])
    )
    assert swarm.size == 2


def test_swarm_add_returns_self_for_chaining() -> None:
    swarm = Swarm(objective="Summarize the design")
    assert swarm.add(Agent(id="lead", role="lead")) is swarm


def test_swarm_run_is_not_implemented_until_p4_9() -> None:
    swarm = Swarm(objective="Summarize the design").add(Agent(id="lead", role="lead"))
    with pytest.raises(NotImplementedError):
        swarm.run()


def test_korch_constructs_with_defaults() -> None:
    # No arguments, no environment — the zero-config path constructs cleanly.
    assert isinstance(Korch(), Korch)


def test_korch_run_is_not_implemented_until_p4_9() -> None:
    with pytest.raises(NotImplementedError):
        Korch().run("Summarize durable agent execution")


def test_korch_accepts_injected_collaborators() -> None:
    from korchestrator.config import Settings

    korch = Korch(settings=Settings(korch_runtime="local"))
    assert isinstance(korch, Korch)
