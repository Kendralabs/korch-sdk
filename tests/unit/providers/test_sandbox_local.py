"""Unit tests for the subprocess-isolating LocalSandbox (spec 03 §5, P4.2).

These spawn short-lived child Python processes (no network, no real model). The timeout test uses a
child that sleeps far longer than the deadline, so the assertion has a wide margin and cannot race.
"""

from __future__ import annotations

import logging
import sys

import pytest

from korchestrator.constants import error_codes as codes
from korchestrator.interfaces import IExecutionSandbox
from korchestrator.providers import LocalSandbox

# Child programs. Each drains stdin first so writing the JSON payload never hits a closed pipe.
_ECHO = "import json, sys; data = json.load(sys.stdin); print(json.dumps({'received': data}))"
_TEXT = "import sys; sys.stdin.read(); print('plain text')"
_FAIL = "import sys; sys.stdin.read(); sys.stderr.write('boom'); sys.exit(2)"
_HANG = "import time; time.sleep(30)"


def _sandbox(program: str, name: str = "tool") -> LocalSandbox:
    return LocalSandbox(commands={name: [sys.executable, "-c", program]})


def test_conforms_to_the_sandbox_port() -> None:
    assert isinstance(LocalSandbox(), IExecutionSandbox)


def test_construction_warns_that_it_is_insecure(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="korchestrator"):
        LocalSandbox()
    assert any(record.message == "sandbox.local.insecure" for record in caplog.records)


async def test_unknown_tool_is_reported_not_raised() -> None:
    result = await LocalSandbox().execute("missing", {})
    assert result.ok is False
    assert result.error_code == codes.TOOL_NOT_FOUND


async def test_successful_run_parses_json_stdout() -> None:
    result = await _sandbox(_ECHO).execute("tool", {"x": 1, "y": "z"})
    assert result.ok is True
    assert result.output == {"received": {"x": 1, "y": "z"}}
    assert result.duration_ms >= 0


async def test_non_json_stdout_is_returned_as_text() -> None:
    result = await _sandbox(_TEXT).execute("tool", {})
    assert result.ok is True
    assert result.output == "plain text"


async def test_nonzero_exit_is_a_failure_with_stderr() -> None:
    result = await _sandbox(_FAIL).execute("tool", {})
    assert result.ok is False
    assert result.error_code == codes.KORCH_PROVIDER_FAILED
    assert result.error is not None and "boom" in result.error


async def test_overrunning_the_deadline_is_a_timeout() -> None:
    result = await _sandbox(_HANG).execute("tool", {}, timeout_seconds=1.0)
    assert result.ok is False
    assert result.error_code == codes.KORCH_TIMEOUT


async def test_unspawnable_command_is_a_provider_failure() -> None:
    sandbox = LocalSandbox(commands={"tool": ["this-executable-does-not-exist-korch"]})
    result = await sandbox.execute("tool", {})
    assert result.ok is False
    assert result.error_code == codes.KORCH_PROVIDER_FAILED
