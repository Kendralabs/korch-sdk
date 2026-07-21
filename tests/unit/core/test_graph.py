"""Unit tests for the AgentGraph topology and its validation (spec 06 §4, P2.4)."""

from __future__ import annotations

import pytest

from korchestrator.core.graph import AgentGraph, Edge, Node
from korchestrator.exceptions import ValidationError
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, StateUpdate


async def _stub_compute(state: AgentState) -> StateUpdate:
    raise NotImplementedError


def _node(node_id: str) -> Node:
    return Node(AgentConfig(id=node_id, persona=AgentPersona(role="r")), _stub_compute)


def test_valid_graph_exposes_sorted_topology() -> None:
    graph = AgentGraph(
        [_node("lead"), _node("security"), _node("perf")],
        [Edge("security", "lead"), Edge("perf", "lead")],
    )
    assert graph.node_ids == ("lead", "perf", "security")
    assert graph.outbound("security") == ("lead",)
    assert graph.outbound("lead") == ()
    assert graph.has_edge("perf", "lead")
    assert not graph.has_edge("lead", "perf")
    assert graph.has_node("lead")
    assert graph.get_node("lead").id == "lead"


def test_empty_graph_is_rejected() -> None:
    with pytest.raises(ValidationError) as info:
        AgentGraph([])
    assert info.value.code == "KORCH_VALIDATION_FAILED"


def test_duplicate_node_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentGraph([_node("dup"), _node("dup")])


def test_edge_to_unknown_node_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentGraph([_node("a")], [Edge("a", "ghost")])
    with pytest.raises(ValidationError):
        AgentGraph([_node("a")], [Edge("ghost", "a")])


def test_self_edge_is_rejected_by_default_but_allowed_by_flag() -> None:
    with pytest.raises(ValidationError):
        AgentGraph([_node("a")], [Edge("a", "a")])
    graph = AgentGraph([_node("a")], [Edge("a", "a")], allow_self_edges=True)
    assert graph.has_edge("a", "a")
    assert graph.allow_self_edges is True


def test_cycles_are_allowed() -> None:
    # A 2-cycle is legal and first-class — the kernel is Pregel, not a DAG runner.
    graph = AgentGraph([_node("a"), _node("b")], [Edge("a", "b"), Edge("b", "a")])
    assert graph.has_edge("a", "b")
    assert graph.has_edge("b", "a")


def test_orphan_node_is_allowed() -> None:
    # A node with no edges runs at superstep 0 then deactivates — not an error.
    graph = AgentGraph([_node("solo")])
    assert graph.node_ids == ("solo",)
    assert graph.outbound("solo") == ()


def test_get_unknown_node_raises() -> None:
    graph = AgentGraph([_node("a")])
    with pytest.raises(ValidationError):
        graph.get_node("missing")
