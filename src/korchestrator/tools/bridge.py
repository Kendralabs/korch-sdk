"""Integration layer (L4). Imports: models, exceptions, constants, tools, logging, stdlib.

The Agent Utility Bridge: :func:`invoke_tool` is the single path every tool call takes. It applies,
in order, the access gate (mounted tools), rate limiting, JSON-Schema argument validation, a
timeout, and an optional Shield redaction seam (filled in P7), then returns a normalised
:class:`ToolResult`.

Expected failures — not mounted, not found, rate-limited, invalid arguments, timeout, or a connector
returning ``ok=False`` — come back as ``ToolResult(ok=False, error_code=...)``. Only an *unexpected*
connector failure surfaces as :class:`ToolError` (spec 07 §6); connectors never bypass the bridge.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Collection, Mapping

from korchestrator.constants import error_codes as codes
from korchestrator.exceptions import ToolError
from korchestrator.models.tool import ToolResult
from korchestrator.tools._ratelimit import RateLimiter
from korchestrator.tools._schema import validate_args
from korchestrator.tools.registry import ConnectorRegistry
from korchestrator.types import JSONValue

__all__ = ["Redactor", "invoke_tool"]

_logger = logging.getLogger("korchestrator.tools")

# The Shield redaction seam: (output) -> (possibly-masked output, whether anything was masked).
# P7's consolidated redactor implements this; until then the bridge runs with no redactor.
Redactor = Callable[[JSONValue], "tuple[JSONValue, bool]"]


async def invoke_tool(
    registry: ConnectorRegistry,
    tool: str,
    args: Mapping[str, JSONValue],
    *,
    tenant_id: str = "default",
    mounted: Collection[str] | None = None,
    timeout_seconds: float = 30.0,
    rate_limiter: RateLimiter | None = None,
    redactor: Redactor | None = None,
    time_source: Callable[[], float] = time.monotonic,
) -> ToolResult:
    """Run one tool call through the bridge and return a normalised :class:`ToolResult`.

    Args:
        registry: Where ``tool`` resolves to a connector.
        tool: The tool name to invoke.
        args: The arguments; validated against the connector's schema before ``execute``.
        tenant_id: Mandatory tenant scope, passed to the connector.
        mounted: The tools the calling agent mounted (``AgentConfig.tools``). When given, a tool not
            in it is invisible and yields ``TOOL_ACCESS_DENIED``. ``None`` imposes no mount gate.
        timeout_seconds: Hard per-call deadline; exceeding it yields a timeout ``ToolResult``.
        rate_limiter: Optional per-tool limiter; a rejected call yields a rate-limited result.
        redactor: Optional Shield seam applied to successful output (P7).
        time_source: Monotonic seconds source for duration/rate-limiting; injected for tests.

    Returns:
        A :class:`ToolResult`. ``ok=False`` with a stable ``error_code`` for every expected failure.

    Raises:
        ToolError: If the connector raises unexpectedly (``TOOL_EXECUTION_FAILED``).

    Example:
        >>> import asyncio
        >>> from korchestrator.tools import ConnectorRegistry, invoke_tool
        >>> async def shout(args):
        ...     return str(args["text"]).upper()
        >>> registry = ConnectorRegistry().register_tool(
        ...     "shout", {"type": "object", "properties": {"text": {"type": "string"}}}, shout
        ... )
        >>> asyncio.run(invoke_tool(registry, "shout", {"text": "hi"})).output
        'HI'
    """
    start = time_source()

    def finish(result: ToolResult) -> ToolResult:
        stamped = result.model_copy(update={"duration_ms": int((time_source() - start) * 1000)})
        _logger.info(
            "tools.invoke",
            extra={
                "tool": tool,
                "tenant_id": tenant_id,
                "ok": stamped.ok,
                "error_code": stamped.error_code,
                "duration_ms": stamped.duration_ms,
            },
        )
        return stamped

    if mounted is not None and tool not in mounted:
        return finish(
            _failure(tool, codes.TOOL_ACCESS_DENIED, "tool is not mounted for this agent")
        )

    connector = registry.resolve(tool)
    if connector is None:
        return finish(_failure(tool, codes.TOOL_NOT_FOUND, "no connector is registered for it"))

    if rate_limiter is not None and not rate_limiter.allow(tool):
        return finish(
            _failure(tool, codes.KORCH_RATE_LIMITED, "the tool's rate limit was exceeded")
        )

    schema_errors = validate_args(connector.schema, args)
    if schema_errors:
        return finish(_failure(tool, codes.KORCH_VALIDATION_FAILED, "; ".join(schema_errors)))

    try:
        result = await asyncio.wait_for(
            connector.execute(tool, args, tenant_id=tenant_id), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        return finish(_failure(tool, codes.KORCH_TIMEOUT, f"exceeded {timeout_seconds}s"))
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(
            f"Tool {tool!r} failed unexpectedly: {exc}. This is a connector bug — a connector must "
            "return ToolResult(ok=False, ...) for expected failures, not raise.",
            code=codes.TOOL_EXECUTION_FAILED,
            tool=tool,
        ) from exc

    return finish(_redact(result, redactor))


def _failure(tool: str, error_code: str, reason: str) -> ToolResult:
    return ToolResult(tool=tool, ok=False, error_code=error_code, error=f"Tool {tool!r}: {reason}.")


def _redact(result: ToolResult, redactor: Redactor | None) -> ToolResult:
    if redactor is None or not result.ok or result.output is None:
        return result
    output, was_redacted = redactor(result.output)
    if not was_redacted:
        return result
    return result.model_copy(update={"output": output, "redacted": True})
