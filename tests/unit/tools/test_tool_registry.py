"""Unit tests for the connector registry and entry-point discovery (P6.1)."""

from __future__ import annotations

import importlib.metadata

import pytest

from korchestrator.exceptions import ValidationError
from korchestrator.tools import ConnectorRegistry, MockSearchConnector
from korchestrator.tools.connectors import Connector

_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}}


async def _echo(args: dict[str, object]) -> object:
    return args.get("text")


def test_register_and_resolve() -> None:
    registry = ConnectorRegistry([MockSearchConnector()])
    assert registry.resolve("web_search").name == "web_search"
    assert "web_search" in registry
    assert registry.resolve("missing") is None


def test_register_tool_wraps_a_callable() -> None:
    registry = ConnectorRegistry().register_tool("echo", _SCHEMA, _echo)
    connector = registry.resolve("echo")
    assert isinstance(connector, Connector)
    assert registry.names() == ("echo",)


def test_duplicate_tool_name_is_rejected() -> None:
    registry = ConnectorRegistry([MockSearchConnector()])
    with pytest.raises(ValidationError):
        registry.register_connector(MockSearchConnector())


def test_discover_registers_good_plugins_and_skips_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEntry:
        def __init__(self, name: str, factory: object) -> None:
            self.name = name
            self._factory = factory

        def load(self) -> object:
            return self._factory

    def good() -> MockSearchConnector:
        return MockSearchConnector()

    def bad() -> MockSearchConnector:
        raise RuntimeError("boom")

    def fake_entry_points(*, group: str) -> list[FakeEntry]:
        assert group == "korchestrator.connectors"
        return [FakeEntry("good", good), FakeEntry("bad", bad)]

    monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)
    registry = ConnectorRegistry().discover()
    assert registry.names() == ("web_search",)  # the good plugin registered; the bad one skipped
