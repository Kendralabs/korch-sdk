"""Unit tests for the built-in connectors (P6.3)."""

from __future__ import annotations

from pathlib import Path

from korchestrator.tools.connectors import Connector, FilesystemConnector, MockSearchConnector


def test_connectors_satisfy_the_protocol() -> None:
    assert isinstance(MockSearchConnector(), Connector)
    assert isinstance(FilesystemConnector("."), Connector)


async def test_filesystem_reads_within_the_root(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    result = await FilesystemConnector(tmp_path).execute("read_file", {"path": "note.txt"})
    assert result.ok is True
    assert result.output == "hello"


async def test_filesystem_denies_traversal(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    root = tmp_path / "sandbox"
    root.mkdir()
    result = await FilesystemConnector(root).execute("read_file", {"path": "../secret.txt"})
    assert result.ok is False
    assert result.error_code == "TOOL_ACCESS_DENIED"


async def test_filesystem_missing_file(tmp_path: Path) -> None:
    result = await FilesystemConnector(tmp_path).execute("read_file", {"path": "nope.txt"})
    assert result.error_code == "TOOL_NOT_FOUND"


async def test_mock_search_is_deterministic() -> None:
    conn = MockSearchConnector()
    first = await conn.execute("web_search", {"query": "durable agents"})
    second = await conn.execute("web_search", {"query": "durable agents"})
    assert first.ok is True
    assert first.output == second.output
    assert len(first.output) == 3
