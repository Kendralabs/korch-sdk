"""Adapter layer. Imports: korchestrator.models/constants/types, stdlib. No optional deps.

The default :class:`~korchestrator.interfaces.IExecutionSandbox` — ``LocalSandbox``: subprocess
isolation for local development (spec 03 §5). A registered tool is an argv command; the sandbox
runs it in a child process, delivers the invocation ``args`` as a JSON document on stdin, bounds it
with a hard timeout (the child is killed on expiry), and returns the child's stdout as a normalised
:class:`~korchestrator.models.tool.ToolResult`.

The child is a separate OS process — a crash or hang cannot take down the caller — but this is a
development fallback, not a hardened sandbox: it does not constrain CPU, memory, filesystem, or
network. It logs a warning on construction and the production-boot gate rejects it under a durable
deployment (spec 08 §5); an enterprise deployment supplies OpenSandbox. The tool registry is empty
until the Agent Utility Bridge (P6) populates it.

This module lives outside workflow scope, so wall-clock timing (:func:`time.monotonic`) is permitted
here — nondeterminism belongs in adapters, never in the kernel (``.claude/rules/determinism.md``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Mapping, Sequence

from korchestrator.constants import error_codes as codes
from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["LocalSandbox"]

_logger = logging.getLogger("korchestrator")

# Bound on captured child stderr placed in ToolResult.error, so a chatty failure cannot produce an
# unbounded payload. The child's output is untrusted input for the caller to validate and redact.
_MAX_ERROR_CHARS = 500


class LocalSandbox:
    """Subprocess-isolating :class:`~korchestrator.interfaces.IExecutionSandbox` for local runs.

    Each registered tool maps to an argv command. :meth:`execute` spawns that command in a child
    process, writes the invocation ``args`` to its stdin as one JSON document, waits up to
    ``timeout_seconds`` (killing the child if it overruns), and returns a
    :class:`~korchestrator.models.tool.ToolResult`. The child's stdout is parsed as JSON when it can
    be, otherwise returned verbatim as text.

    Security: this is a development fallback. It provides process isolation but not resource limits,
    so it logs a warning on construction and the production-boot gate rejects it under a durable
    deployment (spec 08 §5). Supply an enterprise ``IExecutionSandbox`` (OpenSandbox) for anything
    beyond local development. Tool output is untrusted — the caller validates and redacts it.

    Concurrency: safe to call concurrently — each call owns its own child process and the command
    registry is immutable after construction.

    Args:
        commands: A mapping of tool name to the argv used to run it (the executable plus any fixed
            leading arguments). Defaults to empty; the AUB (P6) registers the real tools.

    Example:
        >>> import asyncio, sys
        >>> from korchestrator.providers import LocalSandbox
        >>> sandbox = LocalSandbox(  # doctest: +SKIP
        ...     commands={"echo": [sys.executable, "-c",
        ...                         "import json,sys; print(json.dumps(json.load(sys.stdin)))"]}
        ... )
        >>> asyncio.run(sandbox.execute("echo", {"x": 1})).ok  # doctest: +SKIP
        True
    """

    def __init__(self, *, commands: Mapping[str, Sequence[str]] | None = None) -> None:
        """Freeze the tool→argv registry and warn that this is an unhardened development sandbox."""
        self._commands: dict[str, tuple[str, ...]] = {
            name: tuple(argv) for name, argv in (commands or {}).items()
        }
        _logger.warning(
            "sandbox.local.insecure",
            extra={
                "event": "sandbox.local.insecure",
                "detail": (
                    "LocalSandbox isolates tools in a subprocess but enforces no CPU, memory, "
                    "filesystem, or network limits; it must not be used in a durable deployment."
                ),
            },
        )

    async def execute(
        self,
        tool: str,
        args: Mapping[str, JSONValue],
        *,
        tenant_id: str = "default",
        timeout_seconds: float = 30.0,
    ) -> ToolResult:
        """Run ``tool`` in a child process under a hard timeout; return a :class:`ToolResult`.

        Args:
            tool: The registered tool name to run.
            args: The invocation arguments, delivered to the child as one JSON document on stdin.
            tenant_id: The tenant on whose behalf the tool runs. Accepted for the port contract;
                the local sandbox does not partition by tenant.
            timeout_seconds: Hard deadline. When it elapses the child is killed and the result is a
                failure with :data:`~korchestrator.constants.error_codes.KORCH_TIMEOUT`.

        Returns:
            A :class:`ToolResult`: ``ok=True`` with the parsed stdout as ``output`` on a clean
            exit, otherwise ``ok=False`` with an ``error_code`` and a bounded ``error`` message. The
            method never raises for a tool-level failure — the failure is reported in the result.
        """
        argv = self._commands.get(tool)
        if argv is None:
            return ToolResult(
                tool=tool,
                ok=False,
                error_code=codes.TOOL_NOT_FOUND,
                error=f"Tool '{tool}' is not registered in the local sandbox.",
            )

        payload = json.dumps(dict(args)).encode("utf-8")
        started = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            return ToolResult(
                tool=tool,
                ok=False,
                error_code=codes.KORCH_PROVIDER_FAILED,
                error=f"Could not start tool '{tool}': {exc}.",
                duration_ms=_elapsed_ms(started),
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(payload), timeout=timeout_seconds
            )
        except (asyncio.TimeoutError, TimeoutError):
            proc.kill()
            await proc.wait()
            return ToolResult(
                tool=tool,
                ok=False,
                error_code=codes.KORCH_TIMEOUT,
                error=(
                    f"Tool '{tool}' exceeded its {timeout_seconds:g}s deadline and was terminated."
                ),
                duration_ms=_elapsed_ms(started),
            )

        duration_ms = _elapsed_ms(started)
        if proc.returncode != 0:
            return ToolResult(
                tool=tool,
                ok=False,
                error_code=codes.KORCH_PROVIDER_FAILED,
                error=(
                    f"Tool '{tool}' exited with code {proc.returncode}: "
                    f"{_truncate(stderr.decode('utf-8', 'replace'))}"
                ),
                duration_ms=duration_ms,
            )

        return ToolResult(
            tool=tool,
            ok=True,
            output=_parse_output(stdout),
            duration_ms=duration_ms,
        )


def _elapsed_ms(started: float) -> int:
    """Milliseconds elapsed since ``started`` (a :func:`time.monotonic` reading), never negative."""
    return max(0, int((time.monotonic() - started) * 1000))


def _truncate(text: str) -> str:
    """Bound untrusted child stderr placed in a result message."""
    stripped = text.strip()
    if len(stripped) <= _MAX_ERROR_CHARS:
        return stripped
    return stripped[:_MAX_ERROR_CHARS] + "…"


def _parse_output(stdout: bytes) -> JSONValue:
    """Parse the child's stdout as JSON, falling back to the raw decoded text."""
    text = stdout.decode("utf-8", "replace")
    try:
        parsed: JSONValue = json.loads(text)
    except json.JSONDecodeError:
        return text.strip()
    return parsed
