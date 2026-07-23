"""Contract layer. Imports: korchestrator.types, stdlib, pydantic.

Bitemporal decision/event nodes for the Context Graph (spec 05 §5, P7.6): every recorded fact
carries both ``valid_time`` (when it was true in the world) and ``transaction_time`` (when the
client recorded it), plus ``confidence`` and ``provenance``, so ``persistence.ContextGraphClient``
can answer "what did we believe, and when did we come to believe it" without losing history to a
later correction — a correction is a new node with a later ``transaction_time``, never a mutation
of an earlier one (event sourcing).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["DecisionNode", "EventNode", "GraphNode"]


class GraphNode(BaseModel):
    """The bitemporal shape shared by every Context Graph node.

    Attributes:
        id: The node's unique identifier.
        tenant_id: The tenant this node is scoped to.
        run_id: The run this node relates to, if any.
        content: Free-text content — redacted by ``Shield`` before a node ever reaches this
            field (``persistence.ContextGraphClient``'s job, not the model's).
        provenance: What produced this fact — an agent id, ``"operator"``, a tool name.
        confidence: How confident the source is in this fact, 0.0-1.0.
        valid_time: When this fact was true in the world.
        transaction_time: When the client recorded this fact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    tenant_id: str
    run_id: str | None = None
    content: str
    provenance: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_time: datetime
    transaction_time: datetime


class DecisionNode(GraphNode):
    """An immutable record of a decision the swarm (or an operator) made."""

    kind: Literal["decision"] = "decision"
    rationale: str | None = None


class EventNode(GraphNode):
    """An immutable record of something that happened.

    A message, a tool call, a governance decision — anything the swarm's execution produced.
    """

    kind: Literal["event"] = "event"
    event_type: str
