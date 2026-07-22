"""Façade layer internal (composition root). Imports every layer it wires — the one wiring site.

The shared plumbing behind :class:`Korch` and :class:`Swarm`: resolve the model gateway, turn agents
(or an Architect's plan) into a kernel :class:`AgentGraph` of reasoning nodes, and drive the runtime
to a :class:`RunResult`. Wall-clock and run-id minting live here — the composition root, **not**
workflow scope — injected inward so the kernel stays deterministic (spec 03 §5, determinism).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from korchestrator.agents import Agent, WorkerAgent
from korchestrator.config import Settings
from korchestrator.core.graph import AgentGraph, Edge, Node
from korchestrator.core.pregel import Clock, SuperstepObserver
from korchestrator.exceptions import MissingExtraError, ValidationError
from korchestrator.interfaces import BaseRouter, IDurableRuntime, IModelGateway
from korchestrator.models.agent import AgentConfig
from korchestrator.models.result import RunResult
from korchestrator.models.routing import ModelCard, RoutingContext, TaskSemantics
from korchestrator.models.state import AgentState
from korchestrator.providers import get_lm
from korchestrator.routing import load_model_cards, resolve_router
from korchestrator.runtime import resolve_runtime
from korchestrator.services.hooks import EventHandler, HookRegistry, Middleware
from korchestrator.taxonomy import TaxonomyClassifier
from korchestrator.types import JSONValue

_MIN_OBJECTIVE_CHARS = 10


def build_observer(
    middleware: Sequence[Middleware], handlers: Sequence[tuple[str, EventHandler]]
) -> SuperstepObserver | None:
    """Build a :class:`HookRegistry` from middleware and handlers, or ``None`` if there are none.

    Returning ``None`` when nothing is registered keeps the zero-overhead path — the runtime skips
    observer dispatch entirely.
    """
    if not middleware and not handlers:
        return None
    registry = HookRegistry()
    for item in middleware:
        registry.register_middleware(item)
    for event, handler in handlers:
        registry.on(event, handler)
    return registry


def wall_clock() -> Clock:
    """A monotone UTC wall-clock for the local runtime (composition root — not workflow scope)."""

    def _now() -> datetime:
        return datetime.now(timezone.utc)

    return _now


def resolve_gateway(settings: Settings, gateway: IModelGateway | None) -> IModelGateway:
    """Return the injected gateway, or the one selected from ``settings`` (MockLM by default)."""
    return gateway if gateway is not None else get_lm("korch-default", settings=settings)


def classify(objective: str) -> TaskSemantics:
    """Classify ``objective`` into task semantics for routing (deterministic, offline, no extra)."""
    return TaxonomyClassifier().classify(objective)


def resolve_routing(
    settings: Settings, router: BaseRouter | None
) -> tuple[BaseRouter, tuple[ModelCard, ...]]:
    """Resolve the router (injected or configured) and load the candidate model cards."""
    return resolve_router(settings, router=router), load_model_cards(settings)


def validate_objective(objective: str) -> None:
    """Reject an objective shorter than the kernel's minimum (a fast, offline check)."""
    if len(objective) < _MIN_OBJECTIVE_CHARS:
        raise ValidationError(
            f"Objective must be at least {_MIN_OBJECTIVE_CHARS} characters, got {len(objective)}. "
            "Describe the goal in a sentence, e.g. 'Summarize the Q3 incident reports'."
        )


def worker_node_from_config(
    config: AgentConfig, *, clock: Clock, gateway: IModelGateway, model: str
) -> Node:
    """Build a default :class:`WorkerAgent` from ``config`` with the routed ``model``, as a node."""
    worker = WorkerAgent(
        config.id,
        role=config.persona.role,
        model=model,
        goal=config.persona.goal,
        backstory=config.persona.backstory,
        tools=config.tools,
        max_react_steps=config.max_react_steps,
        hitl_threshold=config.hitl_threshold,
        timeout_seconds=config.timeout_seconds,
    )
    return worker.bind(clock=clock, gateway=gateway).to_node()


async def _route_model(
    router: BaseRouter,
    agent_id: str,
    explicit_model: str | None,
    *,
    task: TaskSemantics,
    candidates: Sequence[ModelCard],
    tenant_id: str,
) -> str:
    """Select the model for one agent through the router (pure w.r.t. context — replay-safe)."""
    context = RoutingContext(
        agent_id=agent_id,
        task=task,
        candidates=tuple(candidates),
        explicit_model=explicit_model,
        tenant_id=tenant_id,
    )
    decision = await router.select_model(context)
    return decision.model_name


async def graph_from_configs(
    configs: Sequence[AgentConfig],
    edges: Sequence[tuple[str, str]],
    *,
    clock: Clock,
    gateway: IModelGateway,
    router: BaseRouter,
    task: TaskSemantics,
    candidates: Sequence[ModelCard],
    tenant_id: str = "default",
) -> AgentGraph:
    """Build a validated :class:`AgentGraph` of default workers from an Architect's plan.

    Each worker's model is selected by the ``router`` at composition time (never workflow scope),
    honouring any model pinned on the plan's :class:`AgentConfig`.
    """
    nodes = []
    for config in configs:
        model = await _route_model(
            router, config.id, config.model, task=task, candidates=candidates, tenant_id=tenant_id
        )
        nodes.append(worker_node_from_config(config, clock=clock, gateway=gateway, model=model))
    return AgentGraph(nodes, [Edge(source, target) for source, target in edges])


async def graph_from_agents(
    agents: Sequence[Agent],
    edges: Sequence[tuple[str, str]],
    *,
    clock: Clock,
    gateway: IModelGateway,
    router: BaseRouter,
    task: TaskSemantics,
    candidates: Sequence[ModelCard],
    tenant_id: str = "default",
) -> AgentGraph:
    """Build a validated :class:`AgentGraph` from user-authored agents (Tier-2 ``Swarm``).

    A declaratively-constructed agent (its ``think`` is the base's) is run by a default
    :class:`WorkerAgent` whose model the ``router`` selects; an agent that overrides ``think`` (a
    custom agent, or a ``WorkerAgent``) supplies its own reasoning and is bound and used directly
    (ADR 0012/0013), so routing does not override it.
    """
    nodes = []
    for agent in agents:
        if type(agent).think is Agent.think:
            model = await _route_model(
                router,
                agent.id,
                agent.config.model,
                task=task,
                candidates=candidates,
                tenant_id=tenant_id,
            )
            nodes.append(
                worker_node_from_config(agent.config, clock=clock, gateway=gateway, model=model)
            )
        else:
            nodes.append(agent.bind(clock=clock, gateway=gateway).to_node())
    return AgentGraph(nodes, [Edge(source, target) for source, target in edges])


async def run_graph(
    graph: AgentGraph,
    *,
    settings: Settings,
    clock: Clock,
    objective: str,
    max_supersteps: int,
    tenant_id: str = "default",
    observer: SuperstepObserver | None = None,
) -> RunResult:
    """Mint a run, resolve the runtime, and drive ``graph`` to its terminal :class:`RunResult`."""
    state = AgentState(
        run_id=uuid.uuid4().hex,
        objective=objective,
        tenant_id=tenant_id,
        transaction_time=clock(),
    )
    runtime = resolve_runtime(settings, graph, clock=clock, observer=observer)
    run_id = await runtime.start(state, max_supersteps=max_supersteps)
    return await runtime.wait(run_id)


def _edit_resume_payload(
    updates: Mapping[str, JSONValue] | None, trust_delta: float
) -> dict[str, str]:
    """Encode an ``edit_resume`` body as the ``Mapping[str, str]`` ``IDurableRuntime.signal`` takes.

    Mirrors ``runtime.temporal_runtime.EditResumePayload``'s shape without importing that module
    at call time for a signal that might not even be ``edit_resume`` — ``send_control_signal``
    only pays the lazy Temporal import when the runtime actually needs it.
    """
    body = json.dumps({"updates": dict(updates or {}), "trust_delta": trust_delta})
    return {"state_update": body}


async def send_control_signal(
    settings: Settings,
    run_id: str,
    name: str,
    *,
    runtime: IDurableRuntime | None = None,
    updates: Mapping[str, JSONValue] | None = None,
    trust_delta: float = 0.0,
) -> None:
    """Deliver a durable HITL control signal (``pause``/``resume``/``cancel``/``edit_resume``).

    Building the full agent graph just to signal an already-running Temporal workflow is
    unnecessary — ``signal()`` only needs a client and the ``run_id``, not the graph (its live
    callables never cross the workflow boundary anyway). ``updates``/``trust_delta`` are only used
    for ``edit_resume``; other signal names ignore them.

    Args:
        settings: Resolved settings; ``korch_runtime`` selects the adapter when ``runtime`` is
            not injected.
        run_id: The run to signal.
        name: ``"pause"``, ``"resume"``, ``"cancel"``, or ``"edit_resume"``.
        runtime: An already-constructed runtime to signal through (e.g. one the caller is also
            using to run graphs). Resolved fresh, graph-less, when omitted.
        updates: ``edit_resume`` only — context-channel values to merge (last-value) into the
            paused run's state.
        trust_delta: ``edit_resume`` only — folded into ``trust_score`` via the same clamp the
            kernel's barrier uses.

    Raises:
        NotImplementedError: On the local runtime, which is synchronous and has no in-flight run
            to signal — durable HITL needs ``KORCH_RUNTIME=temporal``.
        MissingExtraError: If the Temporal runtime is selected without the ``[temporal]`` extra.
    """
    payload = _edit_resume_payload(updates, trust_delta) if name == "edit_resume" else {}
    if runtime is not None:
        await runtime.signal(run_id, name, payload)
        return
    if settings.korch_runtime == "local":
        raise NotImplementedError(
            "The local runtime is synchronous and does not support control signals. "
            "Use the Temporal runtime (KORCH_RUNTIME=temporal) for durable HITL."
        )
    try:
        from korchestrator.runtime.temporal_runtime import TemporalRuntime
    except ImportError as exc:
        raise MissingExtraError(
            "The 'temporal' runtime requires the 'temporal' extra. "
            "Install it with: pip install 'korchestrator[temporal]'",
            code="KORCH_MISSING_EXTRA",
        ) from exc
    control = TemporalRuntime(None, clock=wall_clock())
    await control.signal(run_id, name, payload)
