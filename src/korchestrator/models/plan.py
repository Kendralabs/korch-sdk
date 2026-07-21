"""Contract layer. Imports: korchestrator.models.agent, stdlib, pydantic.

The Architect meta-agent's output: a task decomposition and the ``ExecutionPlan`` (the graph plus
its rationale). Frozen, ``extra="forbid"``, serialised and replayable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.models.agent import AgentConfig

__all__ = [
    "ExecutionPlan",
    "TaskDecomposition",
]


class TaskDecomposition(BaseModel):
    """One unit of work the planner assigned to a named agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    description: str
    assigned_agent: str
    depends_on: tuple[str, ...] = ()
    expected_output: str = ""


class ExecutionPlan(BaseModel):
    """Output of the Architect meta-agent: the graph plus its rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    objective: str = Field(min_length=10)
    intent: str
    difficulty: Literal["trivial", "moderate", "complex"]
    agents: tuple[AgentConfig, ...] = Field(min_length=1)
    edges: tuple[tuple[str, str], ...] = ()
    tasks: tuple[TaskDecomposition, ...] = ()
    max_supersteps: int = Field(default=10, ge=1, le=100)
    rationale: str = ""
