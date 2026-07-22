"""Integration layer (L4). Imports: interfaces, models, types, stdlib.

The :class:`Connector` structural contract every tool provider implements — a superset of the
:class:`~korchestrator.interfaces.AUBConnector` execution protocol that adds the ``name``,
``description`` and JSON-Schema ``schema`` the bridge and registry need. A connector never validates
its own arguments or applies its own timeout/redaction: every call goes through ``tools/bridge.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["Connector"]


@runtime_checkable
class Connector(Protocol):
    """A single named tool: its JSON-Schema for arguments and an ``execute`` implementation.

    Implementations: filesystem, search (with a mock fallback), MCP-backed, and user-defined. A
    connector plugs into the :class:`~korchestrator.tools.registry.ConnectorRegistry` without a core
    edit. ``execute`` MUST NOT raise for *expected* failures — it returns
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

    async def execute(
        self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
    ) -> ToolResult:
        """Invoke ``tool`` with validated ``args`` in ``tenant_id`` and return a ``ToolResult``."""
        ...
