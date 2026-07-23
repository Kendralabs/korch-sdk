"""Contract layer. Imports: korchestrator.models, korchestrator.types, stdlib.

The ``IToolInvoker`` port — the only sanctioned way ``agents/`` reaches a tool. ``agents/``'s
allowed imports (spec 05) are ``core``, ``interfaces``, ``models``, ``exceptions``, ``logging``,
``dspy`` — never ``tools/`` directly, even though ``tools/`` owns the real Agent Utility Bridge.
This mirrors ``IModelGateway`` exactly: a reasoning agent depends on the smallest interface here,
and the composition root injects a concrete adapter that wraps ``tools.invoke_tool`` (P10.2).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Protocol, runtime_checkable

from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["IToolInvoker"]


@runtime_checkable
class IToolInvoker(Protocol):
    """Invoke one mounted tool by name and return its normalised :class:`ToolResult`.

    ARI-style port. The one implementation is ``tools.bridge.RegistryToolInvoker``, which binds a
    ``ConnectorRegistry`` and delegates to ``invoke_tool`` — the mount gate, schema validation,
    timeout, rate limiting, and redaction all still apply; this port only narrows the surface a
    reasoning agent needs down to what ``agents/`` is allowed to import.
    """

    async def invoke_tool(
        self,
        tool: str,
        args: Mapping[str, JSONValue],
        *,
        tenant_id: str,
        mounted: Collection[str],
    ) -> ToolResult:
        """Run ``tool`` with ``args`` in ``tenant_id``, restricted to the ``mounted`` tool names."""
        ...

    def describe_tool(self, tool: str) -> str:
        """Return ``tool``'s human-readable description, or ``""`` if it is not registered.

        A reasoning agent uses this to tell a model what a mounted tool does; synchronous because
        it is metadata lookup, never I/O.
        """
        ...
