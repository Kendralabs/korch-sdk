"""Contract layer. Imports: korchestrator.models, stdlib.

The ``IExecutionSandbox`` ARI port — execute tool code in isolation with a resource and time bound.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["IExecutionSandbox"]


@runtime_checkable
class IExecutionSandbox(Protocol):
    """Execute a tool invocation in isolation, bounded by a timeout and resource limits.

    ARI port. Default implementation: ``providers/sandbox_local.py`` (subprocess isolation); an
    enterprise deployment supplies OpenSandbox.

    Concurrency: implementations MUST be safe to call concurrently and MUST enforce the timeout.
    Tool output is untrusted input — it is returned as a :class:`ToolResult` for the caller to
    validate, redact, and never execute. Tenant scope is mandatory.

    Note: the P1 contract is intentionally minimal; the invocation shape may be enriched, via an
    ADR, when the AUB bridge (P6) and the enterprise sandbox land.
    """

    async def execute(
        self,
        tool: str,
        args: Mapping[str, JSONValue],
        *,
        tenant_id: str = "default",
        timeout_seconds: float = 30.0,
    ) -> ToolResult:
        """Run ``tool`` with ``args`` under isolation; return a :class:`ToolResult`."""
        ...
