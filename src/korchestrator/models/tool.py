"""Contract layer. Imports: korchestrator.types, stdlib, pydantic.

The normalised ``ToolResult`` of one AUB or MCP tool invocation. Frozen and ``extra="forbid"``;
``redacted`` records that Shield masking occurred on the output.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.types import JSONValue

__all__ = ["ToolResult"]


class ToolResult(BaseModel):
    """Normalised outcome of one AUB or MCP tool invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str
    ok: bool
    output: JSONValue = None
    error_code: str | None = None
    error: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    redacted: bool = False
