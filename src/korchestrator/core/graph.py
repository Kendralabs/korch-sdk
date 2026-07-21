"""Kernel layer (L1), framework-free. Imports: korchestrator.models, exceptions, stdlib, pydantic.

The directed agent graph the Pregel kernel runs: ``Node`` (an ``AgentConfig`` plus its bound
compute callable), ``Edge`` (``source -> target``), and ``AgentGraph`` with topology validation.
Cycles are legal and first-class — that is why the kernel is Pregel, not a DAG runner (spec 06 §4).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from korchestrator.exceptions import ValidationError
from korchestrator.models.agent import AgentConfig
from korchestrator.models.state import AgentState, StateUpdate

__all__ = ["AgentCallable", "AgentGraph", "Edge", "Node"]

# The compute function bound to a node: given a frozen state snapshot, return this agent's delta.
# Injected by the composition root — the kernel constructs no agents (spec 03 §5).
AgentCallable = Callable[[AgentState], Awaitable[StateUpdate]]


@dataclass(frozen=True)
class Node:
    """One vertex: an ``AgentConfig`` and the callable that computes its ``StateUpdate``."""

    config: AgentConfig
    compute: AgentCallable

    @property
    def id(self) -> str:
        """The node's identifier (its agent id)."""
        return self.config.id


@dataclass(frozen=True)
class Edge:
    """A directed edge ``source -> target`` between two node ids."""

    source: str
    target: str


class AgentGraph:
    """A validated directed graph of agent nodes and edges.

    Validation runs once at construction (spec 06 §4): at least one node, unique node ids, every
    edge endpoint resolvable to a node, and no self-edge unless ``allow_self_edges=True``. Cycles
    are allowed. Orphan nodes (no edges) are legal — superstep 0 activates every node, so an orphan
    simply runs once and then deactivates.

    Args:
        nodes: The graph's nodes; at least one is required.
        edges: The directed edges. Defaults to no edges.
        allow_self_edges: Permit ``source == target`` edges. Defaults to ``False``.

    Raises:
        ValidationError: If the topology is invalid (empty, duplicate id, dangling edge
            endpoint, or a disallowed self-edge).

    Example:
        >>> from korchestrator.core import AgentGraph, Edge, Node
        >>> from korchestrator.models.agent import AgentConfig, AgentPersona
        >>> async def _noop(state):  # a stub compute callable
        ...     raise NotImplementedError
        >>> cfg = AgentConfig(id="lead", persona=AgentPersona(role="lead"))
        >>> graph = AgentGraph([Node(cfg, _noop)])
        >>> graph.node_ids
        ('lead',)
    """

    def __init__(
        self,
        nodes: Sequence[Node],
        edges: Sequence[Edge] = (),
        *,
        allow_self_edges: bool = False,
    ) -> None:
        """Validate the topology and build the graph's adjacency (spec 06 §4)."""
        if not nodes:
            raise ValidationError(
                "An AgentGraph needs at least one node. Add a Node before running.",
                code="KORCH_VALIDATION_FAILED",
            )

        by_id: dict[str, Node] = {}
        for node in nodes:
            if node.id in by_id:
                raise ValidationError(
                    f"Duplicate node id {node.id!r}. Every node id must be unique in the graph.",
                    code="KORCH_VALIDATION_FAILED",
                )
            by_id[node.id] = node

        for edge in edges:
            for endpoint in (edge.source, edge.target):
                if endpoint not in by_id:
                    raise ValidationError(
                        f"Edge {edge.source!r} -> {edge.target!r} references unknown node "
                        f"{endpoint!r}. Every edge endpoint must be a node in the graph.",
                        code="KORCH_VALIDATION_FAILED",
                    )
            if edge.source == edge.target and not allow_self_edges:
                raise ValidationError(
                    f"Self-edge on node {edge.source!r} is not allowed. Pass "
                    "allow_self_edges=True to permit it.",
                    code="KORCH_VALIDATION_FAILED",
                )

        self._nodes = by_id
        self._edges = tuple(edges)
        self._allow_self_edges = allow_self_edges
        # Precompute adjacency in a deterministic (sorted) order for stable routing.
        outbound: dict[str, list[str]] = {node_id: [] for node_id in by_id}
        for edge in self._edges:
            outbound[edge.source].append(edge.target)
        self._outbound = {src: tuple(sorted(targets)) for src, targets in outbound.items()}

    @property
    def node_ids(self) -> tuple[str, ...]:
        """All node ids, in sorted (deterministic) order."""
        return tuple(sorted(self._nodes))

    @property
    def nodes(self) -> tuple[Node, ...]:
        """All nodes, in sorted-id order."""
        return tuple(self._nodes[node_id] for node_id in self.node_ids)

    @property
    def edges(self) -> tuple[Edge, ...]:
        """All edges, in the order they were supplied."""
        return self._edges

    @property
    def allow_self_edges(self) -> bool:
        """Whether self-edges are permitted in this graph."""
        return self._allow_self_edges

    def get_node(self, node_id: str) -> Node:
        """Return the node with ``node_id``.

        Raises:
            ValidationError: If no such node exists.
        """
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise ValidationError(
                f"No node {node_id!r} in the graph. Known nodes: {', '.join(self.node_ids)}.",
                code="KORCH_VALIDATION_FAILED",
            ) from exc

    def has_node(self, node_id: str) -> bool:
        """Return whether ``node_id`` is a node in the graph."""
        return node_id in self._nodes

    def outbound(self, node_id: str) -> tuple[str, ...]:
        """Return the target ids reachable from ``node_id`` along its outbound edges (sorted)."""
        return self._outbound.get(node_id, ())

    def has_edge(self, source: str, target: str) -> bool:
        """Return whether a directed edge ``source -> target`` exists."""
        return target in self._outbound.get(source, ())
