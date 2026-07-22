"""Canonical AgentGraph fixtures and compute callables for kernel/runtime tests (spec 02 §4).

Shared by the local-runtime, Temporal-runtime, and cross-runtime equivalence tests so they exercise
the exact same topology and agents.
"""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.core import AgentGraph, Edge, Node
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, Message, StateUpdate

FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _node(agent_id: str, compute: object) -> Node:
    return Node(AgentConfig(id=agent_id, persona=AgentPersona(role="r")), compute)  # type: ignore[arg-type]


async def _worker(state: AgentState) -> StateUpdate:
    if state.superstep == 0:
        message = Message(
            id="x",
            sender="x",
            content="data",
            recipient="lead",
            superstep=0,
            valid_time=FIXED_TIME,
        )
        return StateUpdate(agent_id="worker", messages=(message,), valid_time=FIXED_TIME)
    return StateUpdate(agent_id="worker", valid_time=FIXED_TIME)


async def _lead(state: AgentState) -> StateUpdate:
    if state.inbox.get("lead"):
        answer = Message(
            id="x",
            sender="x",
            content="final answer",
            kind="answer",
            superstep=0,
            valid_time=FIXED_TIME,
        )
        return StateUpdate(agent_id="lead", messages=(answer,), halt=True, valid_time=FIXED_TIME)
    return StateUpdate(agent_id="lead", valid_time=FIXED_TIME)


def worker_lead_graph() -> AgentGraph:
    """A worker that messages a lead; the lead answers and halts. Completes in two supersteps."""
    return AgentGraph([_node("lead", _lead), _node("worker", _worker)], [Edge("worker", "lead")])


async def _ping(state: AgentState) -> StateUpdate:
    message = Message(
        id="x", sender="x", content="ping", recipient="b", superstep=0, valid_time=FIXED_TIME
    )
    return StateUpdate(agent_id="a", messages=(message,), valid_time=FIXED_TIME)


async def _pong(state: AgentState) -> StateUpdate:
    message = Message(
        id="x", sender="x", content="pong", recipient="a", superstep=0, valid_time=FIXED_TIME
    )
    return StateUpdate(agent_id="b", messages=(message,), valid_time=FIXED_TIME)


def ping_pong_graph() -> AgentGraph:
    """Two nodes that message each other forever — only ``max_supersteps`` stops it."""
    return AgentGraph([_node("a", _ping), _node("b", _pong)], [Edge("a", "b"), Edge("b", "a")])


def initial_state(run_id: str = "run") -> AgentState:
    """A fresh starting state for the canonical graphs."""
    return AgentState(run_id=run_id, objective="summarize the report", transaction_time=FIXED_TIME)
