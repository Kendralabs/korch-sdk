"""Contract tests for the façade builder surface (P1.5).

These lock the declarative surface — how ``Agent``/``Swarm``/``Korch`` build and validate topology.
Execution (``run``) is exercised end-to-end in ``test_run.py`` (P4.9).
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


def test_agent_rejects_an_invalid_id_with_a_korch_error() -> None:
    # The façade wraps pydantic's error — only KorchError subclasses cross this boundary (A5).
    from pydantic import ValidationError as PydanticValidationError

    from korchestrator import KorchError, ValidationError

    with pytest.raises(ValidationError) as info:
        Agent(id="Upper", role="r")
    assert isinstance(info.value, KorchError)
    assert info.value.code == "KORCH_VALIDATION_FAILED"
    assert isinstance(info.value.__cause__, PydanticValidationError)


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


def test_korch_constructs_with_defaults() -> None:
    # No arguments, no environment — the zero-config path constructs cleanly.
    assert isinstance(Korch(), Korch)


def test_korch_accepts_injected_collaborators() -> None:
    from korchestrator.config import Settings

    korch = Korch(settings=Settings(korch_runtime="local"))
    assert isinstance(korch, Korch)
