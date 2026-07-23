"""Unit tests for the MCP client with an injected fake session (P6.4)."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from unittest import mock

import pytest

from korchestrator.exceptions import MissingExtraError
from korchestrator.mcp import MCPClient, MCPServerConfig
from korchestrator.mcp.client import _default_session_factory
from korchestrator.mcp.session import MCPCallResult, MCPToolSpec
from korchestrator.tools import ConnectorRegistry, invoke_tool
from korchestrator.types import JSONValue

_CONFIG = MCPServerConfig(name="demo", transport="stdio", command="x")


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    async def list_tools(self) -> list[MCPToolSpec]:
        return [
            MCPToolSpec(
                name="echo",
                description="echo back the text",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            )
        ]

    async def call_tool(self, name: str, args: Mapping[str, JSONValue]) -> MCPCallResult:
        if name == "echo":
            return MCPCallResult(output=args.get("text"))
        return MCPCallResult(output="tool errored", is_error=True)

    async def aclose(self) -> None:
        self.closed = True


def _client(session: object) -> MCPClient:
    async def factory(config: MCPServerConfig) -> object:
        return session

    return MCPClient(session_factory=factory)  # type: ignore[arg-type]


async def test_discovered_tool_is_invokable_through_the_bridge() -> None:
    # "An MCP tool loads": discover -> register in the shared registry -> invoke via the bridge.
    connectors = await _client(FakeSession()).discover(_CONFIG)
    registry = ConnectorRegistry(connectors)
    result = await invoke_tool(registry, "echo", {"text": "hi"})
    assert result.ok is True
    assert result.output == "hi"


async def test_mcp_tool_error_becomes_ok_false() -> None:
    class ErrorSession(FakeSession):
        async def call_tool(self, name: str, args: Mapping[str, JSONValue]) -> MCPCallResult:
            return MCPCallResult(output="boom", is_error=True)

    connectors = await _client(ErrorSession()).discover(_CONFIG)
    result = await invoke_tool(ConnectorRegistry(connectors), "echo", {"text": "x"})
    assert result.ok is False
    assert result.error_code == "TOOL_EXECUTION_FAILED"


async def test_mcp_call_raising_becomes_ok_false_execution_failed() -> None:
    class RaisingSession(FakeSession):
        async def call_tool(self, name: str, args: Mapping[str, JSONValue]) -> MCPCallResult:
            raise RuntimeError("transport dropped")

    connectors = await _client(RaisingSession()).discover(_CONFIG)
    result = await invoke_tool(ConnectorRegistry(connectors), "echo", {"text": "x"})
    assert result.ok is False
    assert result.error_code == "TOOL_EXECUTION_FAILED"
    assert result.error is not None
    assert "transport dropped" in result.error


async def test_connector_exposes_the_discovered_name_description_and_schema() -> None:
    (connector,) = await _client(FakeSession()).discover(_CONFIG)
    assert connector.name == "echo"
    assert connector.description == "echo back the text"
    assert connector.schema == {"type": "object", "properties": {"text": {"type": "string"}}}


async def test_discovery_failure_is_skipped_not_fatal() -> None:
    async def failing_factory(config: MCPServerConfig) -> object:
        raise RuntimeError("cannot connect")

    connectors = await MCPClient(session_factory=failing_factory).discover(_CONFIG)  # type: ignore[arg-type]
    assert connectors == []  # skipped; its tools will resolve to TOOL_NOT_FOUND


async def test_missing_extra_propagates() -> None:
    async def missing(config: MCPServerConfig) -> object:
        raise MissingExtraError("install [mcp]")

    with pytest.raises(MissingExtraError):
        await MCPClient(session_factory=missing).discover(_CONFIG)  # type: ignore[arg-type]


async def test_aclose_closes_sessions() -> None:
    session = FakeSession()
    client = _client(session)
    await client.discover(_CONFIG)
    await client.aclose()
    assert session.closed is True


async def test_default_factory_without_the_extra_raises_missing_extra() -> None:
    with (
        mock.patch.dict(sys.modules, {"mcp": None}),
        pytest.raises(MissingExtraError),
    ):
        await _default_session_factory(_CONFIG)
