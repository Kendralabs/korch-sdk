"""Contract tests for models/tool.py (P1.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from korchestrator.models.tool import ToolResult


def test_tool_result_defaults() -> None:
    result = ToolResult(tool="fs.read", ok=True)
    assert result.output is None
    assert result.error_code is None
    assert result.duration_ms == 0
    assert result.redacted is False


def test_tool_result_output_accepts_nested_json() -> None:
    result = ToolResult(tool="search", ok=True, output={"hits": [{"id": 1, "score": None}]})
    assert result.output == {"hits": [{"id": 1, "score": None}]}


def test_tool_result_duration_non_negative() -> None:
    with pytest.raises(ValidationError):
        ToolResult(tool="fs.read", ok=False, duration_ms=-1)


def test_tool_result_is_frozen() -> None:
    result = ToolResult(tool="fs.read", ok=True)
    with pytest.raises(ValidationError):
        result.ok = False  # type: ignore[misc]
