"""Façade layer internal (composition root). Imports every layer it wires — the one wiring site.

The shared plumbing behind :class:`Korch` and :class:`Swarm`: resolve the model gateway, turn agents
(or an Architect's plan) into a kernel :class:`AgentGraph` of reasoning nodes, and drive the runtime
to a :class:`RunResult`. Wall-clock and run-id minting live here — the composition root, **not**
workflow scope — injected inward so the kernel stays deterministic (spec 03 §5, determinism).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from korchestrator.agents import Agent, WorkerAgent
from korchestrator.config import Settings
from korchestrator.core.graph import AgentGraph, Edge, Node
from korchestrator.core.pregel import Clock
from korchestrator.exceptions import ValidationError
from korchestrator.interfaces import IModelGateway
from korchestrator.models.agent import AgentConfig
from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState
from korchestrator.providers import get_lm
from korchestrator.runtime import resolve_runtime

_MIN_OBJECTIVE_CHARS = 10


def wall_clock() -> Clock:
    """A monotone UTC wall-clock for the local runtime (composition root — not workflow scope)."""

    def _now() -> datetime:
        return datetime.now(timezone.utc)

    return _now


def resolve_gateway(settings: Settings, gateway: IModelGateway | None) -> IModelGateway:
    """Return the injected gateway, or the one selected from ``settings`` (MockLM by default)."""
    return gateway if gateway is not None else get_lm("korch-default", settings=settings)


def validate_objective(objective: str) -> None:
    """Reject an objective shorter than the kernel's minimum (a fast, offline check)."""
    if len(objective) < _MIN_OBJECTIVE_CHARS:
        raise ValidationError(
            f"Objective must be at least {_MIN_OBJECTIVE_CHARS} characters, got {len(objective)}. "
            "Describe the goal in a sentence, e.g. 'Summarize the Q3 incident reports'."
        )


def worker_node_from_config(config: AgentConfig, *, clock: Clock, gateway: IModelGateway) -> Node:
    """Build a default :class:`WorkerAgent` from ``config`` and materialise it as a bound node."""
    worker = WorkerAgent(
        config.id,
        role=config.persona.role,
        model=config.model,
        goal=config.persona.goal,
        backstory=config.persona.backstory,
        tools=config.tools,
        max_react_steps=config.max_react_steps,
        hitl_threshold=config.hitl_threshold,
        timeout_seconds=config.timeout_seconds,
    )
    return worker.bind(clock=clock, gateway=gateway).to_node()


def agent_node(agent: Agent, *, clock: Clock, gateway: IModelGateway) -> Node:
    """Materialise an authored ``agent`` as a bound reasoning node.

    A declaratively-constructed agent (its ``think`` is the base's) is run by the default
    :class:`WorkerAgent`; an agent that overrides ``think`` (a custom agent, or a ``WorkerAgent``)
    is bound and used directly (ADR 0012/0013).
    """
    if type(agent).think is Agent.think:
        return worker_node_from_config(agent.config, clock=clock, gateway=gateway)
    return agent.bind(clock=clock, gateway=gateway).to_node()


def graph_from_configs(
    configs: Sequence[AgentConfig],
    edges: Sequence[tuple[str, str]],
    *,
    clock: Clock,
    gateway: IModelGateway,
) -> AgentGraph:
    """Build a validated :class:`AgentGraph` of default workers from an Architect's plan."""
    nodes = [worker_node_from_config(config, clock=clock, gateway=gateway) for config in configs]
    return AgentGraph(nodes, [Edge(source, target) for source, target in edges])


def graph_from_agents(
    agents: Sequence[Agent],
    edges: Sequence[tuple[str, str]],
    *,
    clock: Clock,
    gateway: IModelGateway,
) -> AgentGraph:
    """Build a validated :class:`AgentGraph` from user-authored agents (Tier-2 ``Swarm``)."""
    nodes = [agent_node(agent, clock=clock, gateway=gateway) for agent in agents]
    return AgentGraph(nodes, [Edge(source, target) for source, target in edges])


async def run_graph(
    graph: AgentGraph,
    *,
    settings: Settings,
    clock: Clock,
    objective: str,
    max_supersteps: int,
    tenant_id: str = "default",
) -> RunResult:
    """Mint a run, resolve the runtime, and drive ``graph`` to its terminal :class:`RunResult`."""
    state = AgentState(
        run_id=uuid.uuid4().hex,
        objective=objective,
        tenant_id=tenant_id,
        transaction_time=clock(),
    )
    runtime = resolve_runtime(settings, graph, clock=clock)
    run_id = await runtime.start(state, max_supersteps=max_supersteps)
    return await runtime.wait(run_id)
