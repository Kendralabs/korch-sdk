"""Contract layer. Imports: stdlib, pydantic.

Declarative agent models authored directly by users of the ``Swarm`` builder: the persona, the
per-vertex ``AgentConfig``, and the taxonomy ``AgentDescriptor``. Frozen and ``extra="forbid"``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AgentConfig",
    "AgentDescriptor",
    "AgentPersona",
]


class AgentPersona(BaseModel):
    """Static natural-language identity supplied to a compiled signature."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str = Field(min_length=1)
    goal: str = ""
    backstory: str = ""


class AgentConfig(BaseModel):
    """Declarative configuration of one vertex in an agent graph."""

    # ``protected_namespaces=()`` is required because the field is named ``model``.
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    persona: AgentPersona
    model: str | None = None
    tools: tuple[str, ...] = ()
    max_react_steps: int = Field(default=3, ge=0, le=10)
    hitl_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)


class AgentDescriptor(BaseModel):
    """Taxonomy entry describing what an agent kind is good at."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    description: str
    capabilities: tuple[str, ...] = ()
    intents: tuple[str, ...] = ()
    preferred_models: tuple[str, ...] = ()
