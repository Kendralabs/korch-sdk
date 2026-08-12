"""Integration layer (L4). Imports: interfaces, models, constants, exceptions, mcp (own), logging.

The MCP client. :meth:`MCPClient.discover` connects to a server (via an injected session factory in
tests, or the real ``[mcp]`` transport in production) and returns the server's tools as
:class:`~korchestrator.interfaces.Connector` objects. The composition root registers them in the
shared AUB registry, so agents cannot tell an MCP tool from a native one and progressive disclosure
is just the bridge's mount gate. The client depends on the shared ``Connector`` contract in
``interfaces``, not on ``tools`` — the two feature modules never import each other.

Discovery failures never abort the run: the server is skipped, a ``WARNING`` is logged, and it
contributes no connectors (so its tools resolve to ``TOOL_NOT_FOUND``). A missing ``[mcp]`` extra
raises ``MissingExtraError`` (spec 07 §7).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping

from korchestrator.constants import error_codes as codes
from korchestrator.exceptions import MissingExtraError
from korchestrator.interfaces import Connector
from korchestrator.mcp.config import MCPServerConfig
from korchestrator.mcp.session import MCPCallResult, MCPSession, MCPToolSpec
from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["MCPClient", "SessionFactory"]

_logger = logging.getLogger("korchestrator.mcp")

SessionFactory = Callable[[MCPServerConfig], Awaitable[MCPSession]]


class MCPClient:
    """Discover MCP-server tools as :class:`Connector` objects for the AUB registry.

    Args:
        session_factory: How to open a session for a server. Defaults to the real ``[mcp]``
            transport; inject a fake for offline tests.

    Example:
        >>> import asyncio
        >>> from korchestrator.mcp import MCPClient, MCPServerConfig
        >>> from korchestrator.mcp.session import MCPCallResult, MCPToolSpec
        >>> class FakeSession:
        ...     async def list_tools(self):
        ...         return [MCPToolSpec(name="ping", description="pong")]
        ...     async def call_tool(self, name, args):
        ...         return MCPCallResult(output="pong")
        ...     async def aclose(self):
        ...         pass
        >>> async def factory(config):
        ...     return FakeSession()
        >>> client = MCPClient(session_factory=factory)
        >>> tools = asyncio.run(client.discover(MCPServerConfig(name="demo", command="x")))
        >>> [c.name for c in tools]
        ['ping']
    """

    def __init__(self, *, session_factory: SessionFactory | None = None) -> None:
        """Store the session factory (real ``[mcp]`` transport by default) and open-session list."""
        self._session_factory = session_factory or _default_session_factory
        self._sessions: list[MCPSession] = []

    async def discover(self, config: MCPServerConfig) -> list[Connector]:
        """Connect to ``config`` and return its tools as connectors (empty on any failure).

        A connection or discovery failure is logged and skipped — the server contributes no
        connectors, so the bridge returns ``TOOL_NOT_FOUND`` for its tools. A missing ``[mcp]``
        extra propagates as ``MissingExtraError``.
        """
        try:
            session = await self._session_factory(config)
            specs = await session.list_tools()
        except MissingExtraError:
            raise
        except Exception as exc:
            _logger.warning("mcp.server_skipped", extra={"server": config.name, "error": str(exc)})
            return []
        self._sessions.append(session)
        return [_MCPConnector(session, spec) for spec in specs]

    async def aclose(self) -> None:
        """Close every open MCP session."""
        for session in self._sessions:
            await session.aclose()
        self._sessions.clear()


class _MCPConnector:
    """Adapts one MCP tool into a :class:`Connector` backed by an :class:`MCPSession`."""

    def __init__(self, session: MCPSession, spec: MCPToolSpec) -> None:
        self._session = session
        self._spec = spec

    @property
    def name(self) -> str:
        return self._spec.name

    @property
    def description(self) -> str:
        return self._spec.description

    @property
    def schema(self) -> Mapping[str, JSONValue]:
        return self._spec.input_schema

    async def execute(
        self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
    ) -> ToolResult:
        """Call the MCP tool and normalise the outcome to a :class:`ToolResult`."""
        try:
            result = await self._session.call_tool(self._spec.name, dict(args))
        except Exception as exc:
            return ToolResult(
                tool=tool,
                ok=False,
                error_code=codes.TOOL_EXECUTION_FAILED,
                error=f"MCP call for {tool!r} failed: {exc}",
            )
        return ToolResult(
            tool=tool,
            ok=not result.is_error,
            output=result.output,
            error_code=codes.TOOL_EXECUTION_FAILED if result.is_error else None,
        )


async def _default_session_factory(config: MCPServerConfig) -> MCPSession:  # pragma: no cover
    """Open a real MCP session using the ``[mcp]`` extra (never exercised in base-install CI)."""
    from contextlib import AsyncExitStack

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise MissingExtraError(
            "MCP servers require the 'mcp' extra. Install it with: pip install 'korchestrator[mcp]'"
        ) from exc

    stack = AsyncExitStack()
    if config.transport == "stdio":
        params = StdioServerParameters(
            command=config.command, args=list(config.args), env=dict(config.env) or None
        )
        read, write = await stack.enter_async_context(stdio_client(params))
    else:
        from mcp.client.sse import sse_client

        # Guaranteed by MCPServerConfig's validator.
        assert config.url is not None  # noqa: S101  # nosec B101
        read, write = await stack.enter_async_context(sse_client(config.url))
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return _RealMCPSession(session, stack)


class _RealMCPSession:  # pragma: no cover
    """Wraps an ``mcp`` ``ClientSession`` and its exit stack behind the :class:`MCPSession` seam."""

    def __init__(self, session: object, stack: object) -> None:
        self._session = session
        self._stack = stack

    async def list_tools(self) -> list[MCPToolSpec]:
        result = await self._session.list_tools()  # type: ignore[attr-defined]
        return [
            MCPToolSpec(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema or {},
            )
            for tool in result.tools
        ]

    async def call_tool(self, name: str, args: Mapping[str, JSONValue]) -> MCPCallResult:
        result = await self._session.call_tool(name, dict(args))  # type: ignore[attr-defined]
        texts = [getattr(block, "text", "") for block in getattr(result, "content", [])]
        return MCPCallResult(
            output="\n".join(t for t in texts if t),
            is_error=bool(getattr(result, "isError", False)),
        )

    async def aclose(self) -> None:
        await self._stack.aclose()  # type: ignore[attr-defined]
