"""Contract tests for models/plan.py (P1.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.plan import ExecutionPlan, TaskDecomposition

_AGENT = AgentConfig(id="lead", persona=AgentPersona(role="lead"))


def test_task_decomposition_defaults() -> None:
    task = TaskDecomposition(task_id="t1", description="do it", assigned_agent="lead")
    assert task.depends_on == ()
    assert task.expected_output == ""


def test_execution_plan_valid() -> None:
    plan = ExecutionPlan(
        objective="summarize the incident report",
        intent="summarize",
        difficulty="moderate",
        agents=(_AGENT,),
    )
    assert plan.max_supersteps == 10
    assert plan.schema_version == 1
    assert plan.edges == ()


def test_execution_plan_requires_at_least_one_agent() -> None:
    with pytest.raises(ValidationError):
        ExecutionPlan(
            objective="summarize the incident report",
            intent="summarize",
            difficulty="moderate",
            agents=(),
        )


def test_execution_plan_difficulty_is_constrained() -> None:
    with pytest.raises(ValidationError):
        ExecutionPlan(
            objective="summarize the incident report",
            intent="summarize",
            difficulty="impossible",  # type: ignore[arg-type]
            agents=(_AGENT,),
        )


def test_execution_plan_max_supersteps_bounds() -> None:
    for bad in (0, 101):
        with pytest.raises(ValidationError):
            ExecutionPlan(
                objective="summarize the incident report",
                intent="summarize",
                difficulty="trivial",
                agents=(_AGENT,),
                max_supersteps=bad,
            )
