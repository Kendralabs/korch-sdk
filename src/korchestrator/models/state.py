"""Contract layer. Imports: korchestrator.types, stdlib, pydantic.

The core state models threaded through every superstep: message roles and speech acts, run
status, the immutable ``Message``, the agent-emitted ``StateUpdate`` delta, and the global
``AgentState``. Frozen and ``extra="forbid"`` — the frozen-snapshot rule (spec 05 §5) depends on
it. Fields are the P1 contract; reducer binding and validation land in P2.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.types import JSONValue

__all__ = [
    "AgentState",
    "Message",
    "MessageRole",
    "Performative",
    "RunStatus",
    "StateUpdate",
]


class MessageRole(str, Enum):
    """Origin of a message, mirroring chat-completion roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Performative(str, Enum):
    """FIPA-lite speech act carried by an inter-agent message."""

    INFORM = "inform"
    REQUEST = "request"
    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    QUERY = "query"
    FAILURE = "failure"


class RunStatus(str, Enum):
    """Lifecycle state of a run; the only status vocabulary in the SDK."""

    STARTED = "started"
    RUNNING = "running"
    GOVERNANCE_PAUSED = "governance_paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class Message(BaseModel):
    """One immutable message produced by an agent in a given superstep.

    ``id`` is assigned deterministically by the kernel as
    ``f"{run_id}:{superstep}:{sender}:{index}"`` and ``valid_time`` comes from the runtime's
    injected clock — never a ``uuid4()`` or ``datetime.now()`` default, which would break replay.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: MessageRole = MessageRole.ASSISTANT
    performative: Performative = Performative.INFORM
    kind: Literal["thought", "tool", "answer", "handoff"] = "thought"
    sender: str
    recipient: str | None = None
    content: str
    superstep: int = Field(ge=0)
    valid_time: datetime
    metadata: Mapping[str, JSONValue] = Field(default_factory=dict)


class StateUpdate(BaseModel):
    """The typed delta an agent emits instead of mutating shared state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    updates: Mapping[str, JSONValue] = Field(default_factory=dict)
    messages: tuple[Message, ...] = ()
    halt: bool = False
    trust_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    valid_time: datetime


class AgentState(BaseModel):
    """Global shared state threaded through every superstep."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run_id: str
    tenant_id: str = "default"
    objective: str = Field(min_length=10)
    messages: tuple[Message, ...] = ()
    context: Mapping[str, JSONValue] = Field(default_factory=dict)
    inbox: Mapping[str, tuple[Message, ...]] = Field(default_factory=dict)
    superstep: int = Field(default=0, ge=0)
    halted: bool = False
    halted_agents: tuple[str, ...] = ()
    status: RunStatus = RunStatus.STARTED
    trust_score: float = Field(default=1.0, ge=0.0, le=1.0)
    transaction_time: datetime
