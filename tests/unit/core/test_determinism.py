"""Determinism guarantees for the kernel (spec 06 §5, spec 09 §5, P2.7).

Repeatability (same graph + state + clock -> byte-identical result) and a static check that no
wall-clock read or randomness appears in the workflow-path code (``core/`` and ``models/``).
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Callable
from datetime import datetime, timezone

from korchestrator.core import PregelRunner
from korchestrator.core.graph import AgentGraph, Edge, Node
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, Message, StateUpdate

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _node(agent_id: str, compute: object) -> Node:
    return Node(AgentConfig(id=agent_id, persona=AgentPersona(role="r")), compute)  # type: ignore[arg-type]


async def _worker(state: AgentState) -> StateUpdate:
    if state.superstep == 0:
        msg = Message(
            id="x", sender="x", content="data", recipient="lead", superstep=0, valid_time=NOW
        )
        return StateUpdate(agent_id="worker", messages=(msg,), valid_time=NOW)
    return StateUpdate(agent_id="worker", valid_time=NOW)


async def _lead(state: AgentState) -> StateUpdate:
    if state.inbox.get("lead"):
        answer = Message(
            id="x", sender="x", content="final answer", kind="answer", superstep=0, valid_time=NOW
        )
        return StateUpdate(agent_id="lead", messages=(answer,), halt=True, valid_time=NOW)
    return StateUpdate(agent_id="lead", valid_time=NOW)


def _graph() -> AgentGraph:
    return AgentGraph([_node("lead", _lead), _node("worker", _worker)], [Edge("worker", "lead")])


def _start() -> AgentState:
    return AgentState(run_id="run", objective="summarize the report", transaction_time=NOW)


async def test_the_same_run_is_byte_identical_across_runs(
    make_clock: Callable[..., object],
) -> None:
    first = await PregelRunner(_graph(), clock=make_clock()).run(_start())  # type: ignore[arg-type]
    second = await PregelRunner(_graph(), clock=make_clock()).run(_start())  # type: ignore[arg-type]
    # Assert on the serialised form — it catches ordering differences object equality would hide.
    assert first.model_dump_json() == second.model_dump_json()


# --- no wall clock or randomness in workflow-path code ------------------------------------------

_FORBIDDEN_ATTR_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("date", "today"),
    ("time", "time"),
    ("time", "monotonic"),
    ("uuid", "uuid4"),
}
_FORBIDDEN_MODULES = {"random", "secrets"}
_FORBIDDEN_NAMES = {"uuid4"}


def _forbidden_calls(tree: ast.AST) -> list[str]:
    """Return actual forbidden CALLS (not docstring mentions) found in an AST."""
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if (func.value.id, func.attr) in _FORBIDDEN_ATTR_CALLS:
                hits.append(f"{func.value.id}.{func.attr}()")
            if func.value.id in _FORBIDDEN_MODULES:
                hits.append(f"{func.value.id}.{func.attr}()")
        elif isinstance(func, ast.Name) and func.id in _FORBIDDEN_NAMES:
            hits.append(f"{func.id}()")
    return hits


def test_workflow_path_code_reads_no_wall_clock_or_randomness() -> None:
    # AST-based (not grep) so the explanatory docstring in models/state.py — which mentions
    # datetime.now()/uuid4() precisely to forbid them — does not trip the check.
    offenders: dict[str, list[str]] = {}
    for base in ("src/korchestrator/core", "src/korchestrator/models"):
        for path in sorted(pathlib.Path(base).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = _forbidden_calls(tree)
            if calls:
                offenders[str(path)] = calls
    assert offenders == {}, f"wall-clock/randomness in workflow-path code: {offenders}"
