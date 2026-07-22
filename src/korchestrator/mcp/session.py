"""Integration layer (L4). Imports: types, pydantic, stdlib.

The transport-agnostic MCP session seam. :class:`MCPSession` is the structural contract the client
depends on — list a server's tools and call one — so the discovery/registration mechanics are fully
testable with a fake session, while the real ``mcp`` transport stays behind the ``[mcp]`` extra.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from korchestrator.types import JSONValue

__all__ = ["MCPCallResult", "MCPSession", "MCPToolSpec"]


class MCPToolSpec(BaseModel):
    """A tool advertised by an MCP server: its name, description, and JSON-Schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    input_schema: dict[str, JSONValue] = {}


class MCPCallResult(BaseModel):
    """The normalised outcome of one MCP ``call_tool``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    output: JSONValue = None
    is_error: bool = False


@runtime_checkable
class MCPSession(Protocol):
    """A live connection to one MCP server."""

    async def list_tools(self) -> Sequence[MCPToolSpec]:
        """Return the tools the server advertises."""
        ...

    async def call_tool(self, name: str, args: Mapping[str, JSONValue]) -> MCPCallResult:
        """Invoke ``name`` with ``args`` and return the normalised result."""
        ...

    async def aclose(self) -> None:
        """Close the connection and release its resources."""
        ...
