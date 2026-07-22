"""Contract layer. Imports: korchestrator.models, stdlib.

The tool-execution contracts: ``AUBConnector`` (execute only) and its discovery-aware superset
``Connector`` (adds ``name``/``description``/``schema``). Both the native AUB connectors and the
MCP-backed connectors implement ``Connector`` — it lives here so ``tools`` and ``mcp`` can meet at a
shared contract without importing each other (feature independence).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["AUBConnector", "Connector"]


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


@runtime_checkable
class Connector(AUBConnector, Protocol):
    """A single named tool: an :class:`AUBConnector` that also advertises its name and schema.

    This is the contract the bridge and registry key on. Native connectors and MCP-backed connectors
    both implement it. ``execute`` MUST NOT raise for *expected* failures — it returns
    ``ToolResult(ok=False, error_code=...)``; only unexpected failures propagate (the bridge wraps
    them as ``ToolError``). Arguments are validated by the bridge before ``execute`` is called.
    """

    @property
    def name(self) -> str:
        """The tool name agents mount by (``AgentConfig.tools``) and the registry keys on."""
        ...

    @property
    def description(self) -> str:
        """A short human/model-readable description of what the tool does."""
        ...

    @property
    def schema(self) -> Mapping[str, JSONValue]:
        """The JSON-Schema (object) the bridge validates arguments against."""
        ...
