"""Integration layer (L4).

Allowed imports (beyond stdlib + pydantic): interfaces, models, constants, exceptions, logging;
[mcp] extra (lazy) for the real transport. The MCP client discovers a server's tools and exposes
them as AUB connectors; the composition root registers them. Feature-independent from ``tools`` —
both meet at the ``Connector`` contract in ``interfaces``.
"""

from korchestrator.mcp.client import MCPClient, SessionFactory
from korchestrator.mcp.config import MCPServerConfig
from korchestrator.mcp.session import MCPCallResult, MCPSession, MCPToolSpec

__all__ = [
    "MCPCallResult",
    "MCPClient",
    "MCPServerConfig",
    "MCPSession",
    "MCPToolSpec",
    "SessionFactory",
]
