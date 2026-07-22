"""Unit tests for the AUB bridge invoke_tool (P6.2)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import ClassVar

import pytest

from korchestrator.exceptions import ToolError
from korchestrator.models.tool import ToolResult
from korchestrator.tools import ConnectorRegistry, invoke_tool
from korchestrator.types import JSONValue

_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


async def _echo(args: Mapping[str, JSONValue]) -> JSONValue:
    return str(args["text"]).upper()


def _registry() -> ConnectorRegistry:
    return ConnectorRegistry().register_tool("echo", _SCHEMA, _echo)


async def test_happy_path() -> None:
    result = await invoke_tool(_registry(), "echo", {"text": "hi"})
    assert result.ok is True
    assert result.output == "HI"


async def test_unknown_tool_is_not_found() -> None:
    result = await invoke_tool(_registry(), "nope", {})
    assert result.ok is False
    assert result.error_code == "TOOL_NOT_FOUND"


async def test_unmounted_tool_is_denied() -> None:
    # The mount gate hides tools the agent did not mount, even if registered.
    result = await invoke_tool(_registry(), "echo", {"text": "x"}, mounted=set())
    assert result.error_code == "TOOL_ACCESS_DENIED"


async def test_mounted_tool_is_allowed() -> None:
    result = await invoke_tool(_registry(), "echo", {"text": "x"}, mounted={"echo"})
    assert result.ok is True


async def test_invalid_arguments_are_rejected() -> None:
    result = await invoke_tool(_registry(), "echo", {})  # missing required "text"
    assert result.error_code == "KORCH_VALIDATION_FAILED"


async def test_timeout_is_normalised() -> None:
    class Hang:
        name = "hang"
        description = ""
        schema: ClassVar[dict[str, JSONValue]] = {"type": "object"}

        async def execute(
            self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
        ) -> ToolResult:
            await asyncio.Event().wait()  # never completes
            return ToolResult(tool=tool, ok=True)  # pragma: no cover

    registry = ConnectorRegistry([Hang()])
    result = await invoke_tool(registry, "hang", {}, timeout_seconds=0.0)
    assert result.error_code == "KORCH_TIMEOUT"


async def test_rate_limit_is_enforced() -> None:
    class NeverAllow:
        def allow(self, key: str) -> bool:
            return False

    result = await invoke_tool(_registry(), "echo", {"text": "x"}, rate_limiter=NeverAllow())
    assert result.error_code == "KORCH_RATE_LIMITED"


async def test_connector_ok_false_passes_through() -> None:
    class Failing:
        name = "fail"
        description = ""
        schema: ClassVar[dict[str, JSONValue]] = {"type": "object"}

        async def execute(
            self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
        ) -> ToolResult:
            return ToolResult(tool=tool, ok=False, error_code="TOOL_NOT_FOUND", error="nope")

    result = await invoke_tool(ConnectorRegistry([Failing()]), "fail", {})
    assert result.ok is False
    assert result.error_code == "TOOL_NOT_FOUND"


async def test_unexpected_failure_becomes_tool_error() -> None:
    class Boom:
        name = "boom"
        description = ""
        schema: ClassVar[dict[str, JSONValue]] = {"type": "object"}

        async def execute(
            self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
        ) -> ToolResult:
            raise RuntimeError("kaboom")

    with pytest.raises(ToolError) as info:
        await invoke_tool(ConnectorRegistry([Boom()]), "boom", {})
    assert info.value.code == "TOOL_EXECUTION_FAILED"
    assert info.value.__cause__ is not None


async def test_redactor_masks_output() -> None:
    def redactor(output: JSONValue) -> tuple[JSONValue, bool]:
        return "[MASKED]", True

    result = await invoke_tool(_registry(), "echo", {"text": "secret"}, redactor=redactor)
    assert result.output == "[MASKED]"
    assert result.redacted is True


async def test_duration_is_stamped() -> None:
    clock = iter([0.0, 0.25])
    result = await invoke_tool(_registry(), "echo", {"text": "x"}, time_source=lambda: next(clock))
    assert result.duration_ms == 250
