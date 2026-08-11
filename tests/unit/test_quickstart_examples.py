"""Locks the exact code shown in docs/quickstart.md so a future API change that breaks it is
caught by the normal test suite, not discovered by a reader following the docs (P11.2).
"""

from __future__ import annotations

import pytest

from korchestrator import Agent, Korch, Swarm
from korchestrator.models.state import RunStatus
from korchestrator.providers import MockLM


def test_the_bare_one_liner_completes() -> None:
    pytest.importorskip("dspy")
    result = Korch().run("Summarize durable agent execution in two sentences")
    assert result.status is RunStatus.COMPLETED


def test_the_scripted_mockllm_one_liner_returns_the_scripted_answer() -> None:
    pytest.importorskip("dspy")
    gateway = MockLM(
        default_response=(
            "Durable agent execution means workflows survive crashes and replay "
            "deterministically. It combines a BSP-style kernel with a durable "
            "workflow engine runtime."
        )
    )
    result = Korch(model_gateway=gateway).run("Summarize durable agent execution in two sentences")
    assert result.status is RunStatus.COMPLETED
    assert result.final_answer == (
        "Durable agent execution means workflows survive crashes and replay "
        "deterministically. It combines a BSP-style kernel with a durable "
        "workflow engine runtime."
    )


def test_the_explicit_swarm_topology_completes() -> None:
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
