"""Contract tests for models/agent.py (P1.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.models.agent import AgentConfig, AgentDescriptor, AgentPersona


def test_persona_requires_a_role() -> None:
    assert AgentPersona(role="analyst").goal == ""
    with pytest.raises(ValidationError):
        AgentPersona(role="")


def test_agent_config_defaults() -> None:
    cfg = AgentConfig(id="lead", persona=AgentPersona(role="lead"))
    assert cfg.model is None
    assert cfg.tools == ()
    assert cfg.max_react_steps == 3
    assert cfg.hitl_threshold is None
    assert cfg.timeout_seconds == 120.0


@pytest.mark.parametrize("agent_id", ["lead", "1", "a_b-c", "x" * 64])
def test_agent_config_id_pattern_accepts_valid_ids(agent_id: str) -> None:
    assert AgentConfig(id=agent_id, persona=AgentPersona(role="r")).id == agent_id


@pytest.mark.parametrize("agent_id", ["", "-lead", "UPPER", "has space", "x" * 65])
def test_agent_config_id_pattern_rejects_invalid_ids(agent_id: str) -> None:
    with pytest.raises(ValidationError):
        AgentConfig(id=agent_id, persona=AgentPersona(role="r"))


def test_agent_config_bounds() -> None:
    persona = AgentPersona(role="r")
    with pytest.raises(ValidationError):
        AgentConfig(id="a", persona=persona, max_react_steps=11)
    with pytest.raises(ValidationError):
        AgentConfig(id="a", persona=persona, hitl_threshold=1.5)
    with pytest.raises(ValidationError):
        AgentConfig(id="a", persona=persona, timeout_seconds=0)


def test_agent_config_model_field_is_allowed() -> None:
    # protected_namespaces=() lets the field be named `model` without a pydantic warning.
    cfg = AgentConfig(id="a", persona=AgentPersona(role="r"), model="gpt-4o-mini")
    assert cfg.model == "gpt-4o-mini"


def test_agent_config_is_frozen() -> None:
    cfg = AgentConfig(id="a", persona=AgentPersona(role="r"))
    with pytest.raises(ValidationError):
        cfg.model = "x"  # type: ignore[misc]


def test_agent_descriptor_defaults() -> None:
    desc = AgentDescriptor(id="worker", description="does work")
    assert desc.capabilities == ()
    assert desc.intents == ()
    assert desc.preferred_models == ()
