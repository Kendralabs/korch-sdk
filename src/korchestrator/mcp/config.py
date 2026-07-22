"""Integration layer (L4). Imports: models/pydantic, stdlib.

The connection descriptor for an MCP server. An MCP server is registered by descriptor, not by code
(spec 07 §7): the client connects at composition time, discovers the server's tools, and registers
each as an AUB connector. Frozen and ``extra="forbid"``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator
from typing_extensions import Self

__all__ = ["MCPServerConfig"]


class MCPServerConfig(BaseModel):
    """How to reach one MCP server.

    Args:
        name: A label for logs and duplicate detection.
        transport: ``"stdio"`` (spawn ``command``) or ``"sse"`` (connect to ``url``).
        command: The executable for the stdio transport.
        args: Arguments for the stdio ``command``.
        env: Extra environment for the stdio child process (inert values only).
        url: The endpoint for the sse transport.

    Example:
        >>> MCPServerConfig(name="fs", transport="stdio", command="mcp-fs").transport
        'stdio'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    transport: Literal["stdio", "sse"] = "stdio"
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = {}
    url: str | None = None

    @model_validator(mode="after")
    def _check_transport_fields(self) -> Self:
        if self.transport == "stdio" and not self.command:
            raise ValueError("MCPServerConfig with transport='stdio' requires a 'command'.")
        if self.transport == "sse" and not self.url:
            raise ValueError("MCPServerConfig with transport='sse' requires a 'url'.")
        return self
