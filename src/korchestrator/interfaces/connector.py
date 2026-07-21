"""Contract layer. Imports: korchestrator.models, stdlib.

The ``AUBConnector`` supporting protocol — execute a tool invocation for the Agent Utility Bridge.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["AUBConnector"]


@runtime_checkable
class AUBConnector(Protocol):
    """Execute a single tool invocation and return a normalised ``ToolResult``.

    Implementations: filesystem, search (with a mock fallback), MCP-backed, and user-defined
    connectors, registered in the connector registry (P6). A new connector plugs in without a
    core edit.

    Concurrency: ``execute`` MUST be safe to call concurrently. Arguments are validated against
    the connector's schema before this call; output is untrusted and returned as a
    :class:`ToolResult` for the bridge to redact. ``tenant_id`` is mandatory scope.

    Note: the P1 contract passes tenant scope explicitly; a richer invocation context may be
    introduced, via an ADR, when the AUB bridge lands (P6.2).
    """

    async def execute(
        self,
        tool: str,
        args: Mapping[str, JSONValue],
        *,
        tenant_id: str = "default",
    ) -> ToolResult:
        """Invoke ``tool`` with ``args`` in ``tenant_id``; return a :class:`ToolResult`."""
        ...
