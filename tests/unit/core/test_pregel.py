"""Unit tests for the Pregel superstep runner (spec 06 §1-§4, P2.3/P2.5/P2.6)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from korchestrator.core import Append, ChannelSchema, PregelRunner
from korchestrator.core.graph import AgentGraph, Edge, Node
from korchestrator.exceptions import ValidationError
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, Message, StateUpdate
from korchestrator.types import JSONValue

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _node(agent_id: str, compute: object) -> Node:
    return Node(AgentConfig(id=agent_id, persona=AgentPersona(role="r")), compute)  # type: ignore[arg-type]


def _update(
    agent_id: str,
    *,
    updates: dict[str, JSONValue] | None = None,
    messages: Sequence[Message] = (),
    halt: bool = False,
    trust_delta: float = 0.0,
) -> StateUpdate:
    return StateUpdate(
        agent_id=agent_id,
        updates=updates or {},
        messages=tuple(messages),
        halt=halt,
        trust_delta=trust_delta,
        valid_time=NOW,
    )


def _msg(content: str, *, recipient: str | None = None, kind: str = "thought") -> Message:
    return Message(
        id="placeholder",
        sender="placeholder",
        content=content,
        recipient=recipient,
        kind=kind,  # type: ignore[arg-type]
        superstep=0,
        valid_time=NOW,
    )


def _echo(
    agent_id: str,
    *,
    updates: dict[str, JSONValue] | None = None,
    messages: Sequence[Message] = (),
    halt: bool = False,
    trust_delta: float = 0.0,
) -> Callable[[AgentState], object]:
    async def compute(state: AgentState) -> StateUpdate:
        return _update(
            agent_id, updates=updates, messages=messages, halt=halt, trust_delta=trust_delta
        )

    return compute


def _start(run_id: str = "run", objective: str = "summarize the report") -> AgentState:
    return AgentState(run_id=run_id, objective=objective, transaction_time=NOW)


# --- the canonical worker -> lead graph ---------------------------------------------------------


async def _worker(state: AgentState) -> StateUpdate:
    if state.superstep == 0:
        return _update("worker", messages=[_msg("data", recipient="lead")])
    return _update("worker")


async def _lead(state: AgentState) -> StateUpdate:
    if state.inbox.get("lead"):
        return _update("lead", messages=[_msg("final answer", kind="answer")], halt=True)
    return _update("lead")


def _worker_lead_graph() -> AgentGraph:
    return AgentGraph([_node("lead", _lead), _node("worker", _worker)], [Edge("worker", "lead")])


# --- activation ---------------------------------------------------------------------------------


def test_superstep_zero_activates_all_nodes(make_clock: Callable[..., object]) -> None:
    graph = AgentGraph([_node("a", _echo("a")), _node("b", _echo("b"))])
    runner = PregelRunner(graph, clock=make_clock())  # type: ignore[arg-type]
    assert runner.active_node_ids(_start()) == ("a", "b")


def test_later_supersteps_activate_only_inbox_nodes(make_clock: Callable[..., object]) -> None:
    graph = AgentGraph([_node("a", _echo("a")), _node("b", _echo("b"))], [Edge("a", "b")])
    runner = PregelRunner(graph, clock=make_clock())  # type: ignore[arg-type]
    delivered = _msg("hi").model_copy(update={"id": "run:0:a:0", "sender": "a"})
    state = _start().model_copy(update={"superstep": 1, "inbox": {"b": (delivered,)}})
    assert runner.active_node_ids(state) == ("b",)


def test_a_halted_node_is_never_reactivated(make_clock: Callable[..., object]) -> None:
    graph = AgentGraph([_node("a", _echo("a")), _node("b", _echo("b"))], [Edge("a", "b")])
    runner = PregelRunner(graph, clock=make_clock())  # type: ignore[arg-type]
    delivered = _msg("hi").model_copy(update={"id": "run:0:a:0", "sender": "a"})
    state = _start().model_copy(
        update={"superstep": 1, "inbox": {"b": (delivered,)}, "halted_agents": ("b",)}
    )
    assert runner.active_node_ids(state) == ()


# --- halting ------------------------------------------------------------------------------------


async def test_run_completes_when_all_active_nodes_halt(
    make_clock: Callable[..., object],
) -> None:
    result = await PregelRunner(_worker_lead_graph(), clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert result.status.value == "completed"
    assert result.supersteps == 2
    assert result.final_answer == "final answer"
    assert result.error_code is None


async def test_run_completes_when_no_node_is_active(make_clock: Callable[..., object]) -> None:
    # A single node that emits nothing deactivates after superstep 0 (no messages routed).
    graph = AgentGraph([_node("solo", _echo("solo"))])
    result = await PregelRunner(graph, clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert result.status.value == "completed"
    assert result.supersteps == 1
    assert result.error_code is None


async def test_run_halts_at_max_supersteps(make_clock: Callable[..., object]) -> None:
    # A ping-pong graph never halts on its own; the max_supersteps bound stops it.
    graph = AgentGraph(
        [
            _node("a", _echo("a", messages=[_msg("ping", recipient="b")])),
            _node("b", _echo("b", messages=[_msg("pong", recipient="a")])),
        ],
        [Edge("a", "b"), Edge("b", "a")],
    )
    result = await PregelRunner(graph, clock=make_clock(), max_supersteps=3).run(_start())  # type: ignore[arg-type]
    assert result.status.value == "completed"
    assert result.supersteps == 3
    assert result.error_code == "MAX_SUPERSTEPS_REACHED"


# --- reduce -------------------------------------------------------------------------------------


async def test_context_channels_merge_through_their_reducer(
    make_clock: Callable[..., object],
) -> None:
    graph = AgentGraph(
        [
            _node("a", _echo("a", updates={"log": "a-note"}, halt=True)),
            _node("b", _echo("b", updates={"log": "b-note"}, halt=True)),
        ]
    )
    runner = PregelRunner(
        graph,
        clock=make_clock(),  # type: ignore[arg-type]
        channels=ChannelSchema({"log": Append()}),
    )
    result = await runner.run(_start())
    assert result.state.context["log"] == ["a-note", "b-note"]


# --- trust scoring (spec 05 §3.1, P7.2) ----------------------------------------------------------


async def test_trust_score_starts_at_one_and_persists_with_no_delta(
    make_clock: Callable[..., object],
) -> None:
    result = await PregelRunner(_worker_lead_graph(), clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert result.trust_score == 1.0


async def test_trust_delta_lowers_the_trust_score(make_clock: Callable[..., object]) -> None:
    graph = AgentGraph([_node("a", _echo("a", trust_delta=-0.3, halt=True))])
    result = await PregelRunner(graph, clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert result.trust_score == pytest.approx(0.7)


async def test_trust_score_accumulates_across_supersteps(
    make_clock: Callable[..., object],
) -> None:
    # Superstep 0 activates every node, so a lone sender/receiver pair both contribute in the same
    # round; a ping-pong (each halts only once it has heard back) genuinely spans two supersteps.
    async def ping(state: AgentState) -> StateUpdate:
        return _update(
            "a", messages=[_msg("ping", recipient="b")], trust_delta=-0.1, halt=state.superstep > 0
        )

    async def pong(state: AgentState) -> StateUpdate:
        return _update(
            "b", messages=[_msg("pong", recipient="a")], trust_delta=-0.1, halt=state.superstep > 0
        )

    graph = AgentGraph(
        [
            Node(AgentConfig(id="a", persona=AgentPersona(role="r")), ping),  # type: ignore[arg-type]
            Node(AgentConfig(id="b", persona=AgentPersona(role="r")), pong),  # type: ignore[arg-type]
        ],
        [Edge("a", "b"), Edge("b", "a")],
    )
    result = await PregelRunner(graph, clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert result.supersteps == 2
    assert result.trust_score == pytest.approx(0.6)


async def test_trust_score_is_clamped_at_zero(make_clock: Callable[..., object]) -> None:
    graph = AgentGraph(
        [
            _node("a", _echo("a", trust_delta=-1.0, halt=True)),
            _node("b", _echo("b", trust_delta=-1.0, halt=True)),
        ]
    )
    result = await PregelRunner(graph, clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert result.trust_score == 0.0


async def test_trust_score_is_clamped_at_one(make_clock: Callable[..., object]) -> None:
    graph = AgentGraph([_node("a", _echo("a", trust_delta=1.0, halt=True))])
    result = await PregelRunner(graph, clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert result.trust_score == 1.0


_TRUST_DELTA = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@given(st.lists(_TRUST_DELTA, min_size=1, max_size=4))
@settings(deadline=None, max_examples=25)
def test_trust_score_aggregation_is_order_independent_and_clamped(deltas: list[float]) -> None:
    """Reducer-law discipline (spec 06 §3) applied to the scalar trust score: the barrier's fold
    over each superstep's ``trust_delta``\\ s must not depend on node order, only on the multiset
    of deltas, and must stay within ``[0.0, 1.0]``."""

    async def run_with_order(order: Sequence[float]) -> float:
        nodes = [
            _node(f"a{i}", _echo(f"a{i}", trust_delta=d, halt=True)) for i, d in enumerate(order)
        ]
        result = await PregelRunner(AgentGraph(nodes), clock=lambda: NOW).run(_start())
        return result.trust_score

    forward = asyncio.run(run_with_order(deltas))
    backward = asyncio.run(run_with_order(list(reversed(deltas))))
    expected = max(0.0, min(1.0, 1.0 + sum(deltas)))
    assert forward == pytest.approx(expected)
    assert backward == pytest.approx(forward)


# --- message routing ----------------------------------------------------------------------------


async def test_broadcast_delivers_to_every_outbound_edge(
    make_clock: Callable[..., object],
) -> None:
    graph = AgentGraph(
        [
            _node("a", _echo("a", messages=[_msg("hi")])),
            _node("b", _echo("b")),
            _node("c", _echo("c")),
        ],
        [Edge("a", "b"), Edge("a", "c")],
    )
    state = await PregelRunner(graph, clock=make_clock()).run_superstep(_start())  # type: ignore[arg-type]
    assert set(state.inbox) == {"b", "c"}
    assert state.inbox["b"][0].content == "hi"


async def test_directed_message_delivers_only_to_its_recipient(
    make_clock: Callable[..., object],
) -> None:
    graph = AgentGraph(
        [
            _node("a", _echo("a", messages=[_msg("hi", recipient="b")])),
            _node("b", _echo("b")),
            _node("c", _echo("c")),
        ],
        [Edge("a", "b"), Edge("a", "c")],
    )
    state = await PregelRunner(graph, clock=make_clock()).run_superstep(_start())  # type: ignore[arg-type]
    assert set(state.inbox) == {"b"}


async def test_directed_message_without_an_edge_is_rejected(
    make_clock: Callable[..., object],
) -> None:
    graph = AgentGraph(
        [
            _node("a", _echo("a", messages=[_msg("hi", recipient="c")])),
            _node("b", _echo("b")),
            _node("c", _echo("c")),
        ],
        [Edge("a", "b")],
    )
    with pytest.raises(ValidationError):
        await PregelRunner(graph, clock=make_clock()).run_superstep(_start())  # type: ignore[arg-type]


async def test_message_ids_are_assigned_deterministically(
    make_clock: Callable[..., object],
) -> None:
    graph = AgentGraph(
        [_node("a", _echo("a", messages=[_msg("hi")])), _node("b", _echo("b"))],
        [Edge("a", "b")],
    )
    state = await PregelRunner(graph, clock=make_clock()).run_superstep(_start(run_id="R"))  # type: ignore[arg-type]
    assert state.inbox["b"][0].id == "R:0:a:0"
    assert state.inbox["b"][0].sender == "a"


async def test_answer_messages_accumulate_into_the_final_answer(
    make_clock: Callable[..., object],
) -> None:
    result = await PregelRunner(_worker_lead_graph(), clock=make_clock()).run(_start())  # type: ignore[arg-type]
    assert [m.content for m in result.messages if m.kind == "answer"] == ["final answer"]


# --- synchronise validation ---------------------------------------------------------------------


async def test_update_with_a_foreign_agent_id_is_rejected(
    make_clock: Callable[..., object],
) -> None:
    # Node "a" wrongly emits a StateUpdate for "impostor".
    graph = AgentGraph([_node("a", _echo("impostor"))])
    with pytest.raises(ValidationError):
        await PregelRunner(graph, clock=make_clock()).run_superstep(_start())  # type: ignore[arg-type]


# --- frozen snapshot ----------------------------------------------------------------------------


def test_the_state_snapshot_is_frozen() -> None:
    state = _start()
    with pytest.raises(PydanticValidationError):
        state.superstep = 99  # type: ignore[misc]
