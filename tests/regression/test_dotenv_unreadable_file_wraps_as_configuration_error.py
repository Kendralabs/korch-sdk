"""Regression: an unreadable .env file used to let a raw OSError escape Settings.from_env.

**Issue.** `_read_dotenv_file` (`src/korchestrator/config/settings.py`) called
`Path.read_text()` with no error handling around it — a permissions error or any other OS-level
read failure would propagate as a bare `OSError` straight out of `Settings.from_env`, crossing a
public boundary with an unwrapped, non-actionable exception (violating the "everything catchable is
a `KorchError` subclass" rule). Fixed in the P8.4 exception audit.

**Fix.** The read is now wrapped: any `OSError` raises `ConfigurationError` naming the file path,
the underlying error, and the escape hatch (`dotenv_path=None`), with `__cause__` preserved. See the
P8.4 engineering-log entry and CHANGELOG's "Exception audit (Phase 8)" line.

This test locks it directly by monkeypatching `Path.read_text` to fail — deterministic and portable
(T1/T2), unlike relying on real filesystem permissions, which behave inconsistently across OSes.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError


def test_an_unreadable_dotenv_file_raises_configuration_error_not_a_bare_oserror(
    tmp_path: Path,
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("MOCK_LLM=true\n", encoding="utf-8")

    with (
        mock.patch.object(Path, "read_text", side_effect=OSError("permission denied")),
        pytest.raises(ConfigurationError) as info,
    ):
        Settings.from_env(dotenv_path=dotenv)

    assert str(dotenv) in str(info.value)
    assert "dotenv_path=None" in str(info.value)
    assert isinstance(info.value.__cause__, OSError)
