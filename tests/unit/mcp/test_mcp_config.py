"""Unit tests for the MCP server descriptor (P6.4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.mcp import MCPServerConfig


def test_stdio_requires_a_command() -> None:
    with pytest.raises(ValidationError):
        MCPServerConfig(name="fs", transport="stdio")


def test_sse_requires_a_url() -> None:
    with pytest.raises(ValidationError):
        MCPServerConfig(name="remote", transport="sse")


def test_valid_stdio_config() -> None:
    config = MCPServerConfig(name="fs", transport="stdio", command="mcp-fs", args=("--root", "/x"))
    assert config.command == "mcp-fs"
    assert config.args == ("--root", "/x")


def test_valid_sse_config() -> None:
    config = MCPServerConfig(name="remote", transport="sse", url="https://mcp.test/sse")
    assert config.url == "https://mcp.test/sse"
