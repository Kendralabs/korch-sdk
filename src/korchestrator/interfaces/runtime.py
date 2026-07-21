"""Contract layer. Imports: korchestrator.models, stdlib.

The ``IDurableRuntime`` supporting protocol — drive the superstep loop with a durability guarantee.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from korchestrator.models.result import RunResult
from korchestrator.models.state import AgentState

__all__ = ["IDurableRuntime"]


@runtime_checkable
class IDurableRuntime(Protocol):
    """Drive the Pregel superstep loop to a terminal or paused ``RunResult``.

    Implementations: ``runtime/local_runtime.py`` (in-process, the default) and
    ``runtime/temporal_runtime.py`` (durable, behind ``[temporal]``).

    The graph, the model gateway, and the injected clock are supplied to the concrete runtime at
    construction — the runtime constructs no collaborators. ``run`` therefore takes only the
    initial :class:`AgentState`; it never references the ``core`` graph type, keeping this
    contract dependent on ``models`` alone.

    Determinism: workflow-scope code inside an implementation MUST use the injected clock and no
    randomness; all nondeterminism lives in activities (spec 06).
    """

    async def run(self, state: AgentState, *, max_supersteps: int = 10) -> RunResult:
        """Run the superstep loop from ``state`` and return the terminal (or paused) result."""
        ...
