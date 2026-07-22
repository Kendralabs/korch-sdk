"""Integration layer (L4). Imports: interfaces, models, types, exceptions, logging, stdlib.

The :class:`ConnectorRegistry` — the one place a tool name resolves to the connector that runs it.
Populated by constructor injection (``Korch(connectors=[...])``), explicit registration, or
entry-point discovery (``korchestrator.connectors``). Registration is via this registry, not a
process-global (ADR 0015); a discovery failure is logged and skipped, never fatal.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping

from typing_extensions import Self

from korchestrator.exceptions import ValidationError
from korchestrator.models.tool import ToolResult
from korchestrator.tools.connectors.base import Connector
from korchestrator.types import JSONValue

__all__ = ["ENTRY_POINT_GROUP", "ConnectorRegistry"]

ENTRY_POINT_GROUP = "korchestrator.connectors"

_logger = logging.getLogger("korchestrator.tools")

ToolFunction = Callable[[Mapping[str, JSONValue]], Awaitable[JSONValue]]


class ConnectorRegistry:
    """Resolve a tool name to the :class:`Connector` that executes it.

    Args:
        connectors: Connectors to register up front.

    Raises:
        ValidationError: If two connectors claim the same tool name.

    Example:
        >>> import asyncio
        >>> from korchestrator.models.tool import ToolResult
        >>> from korchestrator.tools import ConnectorRegistry
        >>> async def shout(args):
        ...     return str(args["text"]).upper()
        >>> registry = ConnectorRegistry().register_tool(
        ...     "shout", {"type": "object", "properties": {"text": {"type": "string"}}}, shout
        ... )
        >>> registry.resolve("shout").name
        'shout'
    """

    def __init__(self, connectors: Iterable[Connector] = ()) -> None:
        """Build the registry and register any initial connectors."""
        self._by_name: dict[str, Connector] = {}
        for connector in connectors:
            self.register_connector(connector)

    def register_connector(self, connector: Connector) -> Self:
        """Register ``connector`` under its ``name``; return ``self`` for chaining.

        Raises:
            ValidationError: If the tool name is already registered.
        """
        self._reserve(connector.name)
        self._by_name[connector.name] = connector
        return self

    def register_tool(
        self,
        name: str,
        schema: Mapping[str, JSONValue],
        function: ToolFunction,
        *,
        description: str = "",
    ) -> Self:
        """Register a bare async ``function`` as the tool ``name``; return ``self`` for chaining.

        The function receives the validated arguments and returns the tool output; the bridge wraps
        it in a successful :class:`ToolResult`. For expected-failure control (``ok=False``),
        implement a full :class:`Connector` instead.

        Raises:
            ValidationError: If the tool name is already registered.
        """
        self._reserve(name)
        self._by_name[name] = _CallableConnector(name, description, dict(schema), function)
        return self

    def resolve(self, tool: str) -> Connector | None:
        """Return the connector registered for ``tool``, or ``None`` if unknown."""
        return self._by_name.get(tool)

    def names(self) -> tuple[str, ...]:
        """Return the registered tool names, sorted for deterministic listing."""
        return tuple(sorted(self._by_name))

    def __contains__(self, tool: object) -> bool:
        """Whether ``tool`` names a registered connector."""
        return tool in self._by_name

    def discover(self, *, group: str = ENTRY_POINT_GROUP) -> Self:
        """Register connectors advertised by installed packages via entry points.

        Each entry point is a zero-argument factory returning a :class:`Connector`. A factory that
        fails to load, build, or that duplicates a name is logged at ``WARNING`` and skipped, so
        third-party discovery never aborts startup. Returns ``self`` for chaining.
        """
        from importlib.metadata import entry_points

        for entry in entry_points(group=group):
            try:
                connector = entry.load()()
                self.register_connector(connector)
            except Exception as exc:
                # A bad third-party plugin must never abort startup; skip it and warn.
                _logger.warning(
                    "tools.connector_discovery_failed",
                    extra={"entry_point": entry.name, "error": str(exc)},
                )
        return self

    def _reserve(self, name: str) -> None:
        if name in self._by_name:
            raise ValidationError(
                f"A connector for tool {name!r} is already registered. Tool names are unique; "
                "rename one connector or register it once."
            )


class _CallableConnector:
    """Adapts a bare async function into a :class:`Connector` (used by ``register_tool``)."""

    def __init__(
        self,
        name: str,
        description: str,
        schema: Mapping[str, JSONValue],
        function: ToolFunction,
    ) -> None:
        self._name = name
        self._description = description
        self._schema = schema
        self._function = function

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def schema(self) -> Mapping[str, JSONValue]:
        return self._schema

    async def execute(
        self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
    ) -> ToolResult:
        output = await self._function(args)
        return ToolResult(tool=tool, ok=True, output=output)
