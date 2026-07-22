"""Contract layer. Imports: korchestrator.models, stdlib.

The ``IDurableRuntime`` supporting protocol — own the superstep loop with a durability guarantee,
its replay-safe clock, and its control signals (spec 06 §6; shape amended in ADR 0010).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol, runtime_checkable

from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState

__all__ = ["IDurableRuntime"]


@runtime_checkable
class IDurableRuntime(Protocol):
    """Execute a Pregel run and own its durability, timing, and control signals.

    Implementations: ``runtime/local_runtime.py`` (in-process, the default) and
    ``runtime/temporal_runtime.py`` (durable, behind ``[temporal]``).

    The graph, the model gateway, the channel schema, and the clock are supplied to the concrete
    runtime **at construction** — the runtime constructs no collaborators, and this protocol never
    references the ``core`` graph type, keeping the contract dependent on ``models`` alone (ADR 0010
    resolves spec 06 §6's ``start(graph, ...)`` against the inward-only layering rule).

    Determinism: workflow-scope code inside an implementation MUST use :meth:`now` for time and no
    randomness; all nondeterminism lives in activities (spec 06 §5).
    """

    def now(self) -> datetime:
        """Return the replay-safe current time. NEVER ``datetime.now()``."""
        ...

    async def start(self, state: AgentState, *, max_supersteps: int = 10) -> str:
        """Begin a run from ``state`` and return its stable ``run_id`` without waiting."""
        ...

    async def wait(self, run_id: str, *, timeout_seconds: float | None = None) -> RunResult:
        """Block until ``run_id`` reaches a terminal or paused state and return its result."""
        ...

    async def signal(self, run_id: str, name: str, payload: Mapping[str, str]) -> None:
        """Deliver a durable control signal (``resume``, ``cancel``, ``edit_resume``)."""
        ...
