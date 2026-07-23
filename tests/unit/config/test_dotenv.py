"""Unit tests for ``.env`` file loading (spec 08 §1.1/§1.3, ADR 0016).

``.env`` support is opt-in on ``Settings.from_env()`` (``dotenv_path=None`` by default), so these
tests always pass an explicit path to a controlled file — no ambient developer ``.env`` can affect
them, and no other test's bare ``from_env()`` call is affected by ``.env`` loading at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from korchestrator.config import Settings

_ENV_VARS = ("KORCH_RUNTIME", "PERSISTENCE_BACKEND")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_from_env_with_no_dotenv_path_never_touches_the_filesystem(tmp_path: Path) -> None:
    # dotenv_path=None (the default) is a pure, file-free call even when a .env sits right there.
    (tmp_path / ".env").write_text("KORCH_RUNTIME=temporal\n", encoding="utf-8")
    assert Settings.from_env().korch_runtime == "local"


def test_a_missing_dotenv_file_is_not_an_error(tmp_path: Path) -> None:
    settings = Settings.from_env(dotenv_path=tmp_path / "does-not-exist.env")
    assert settings.korch_runtime == "local"


def test_dotenv_values_are_read(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("KORCH_RUNTIME=temporal\nPERSISTENCE_BACKEND=none\n", encoding="utf-8")
    settings = Settings.from_env(dotenv_path=dotenv)
    assert settings.korch_runtime == "temporal"
    assert settings.persistence_backend == "none"


def test_blank_lines_and_comments_are_ignored(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# a comment\n\nKORCH_RUNTIME=temporal\n   \n# PERSISTENCE_BACKEND=none\n",
        encoding="utf-8",
    )
    settings = Settings.from_env(dotenv_path=dotenv)
    assert settings.korch_runtime == "temporal"
    assert settings.persistence_backend == "memory"  # the commented line never applied


def test_quoted_values_have_their_quotes_stripped(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text('KORCH_RUNTIME="temporal"\n', encoding="utf-8")
    assert Settings.from_env(dotenv_path=dotenv).korch_runtime == "temporal"


def test_a_real_environment_variable_wins_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("KORCH_RUNTIME=temporal\n", encoding="utf-8")
    monkeypatch.setenv("KORCH_RUNTIME", "local")
    assert Settings.from_env(dotenv_path=dotenv).korch_runtime == "local"


def test_an_explicit_override_wins_over_dotenv(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("KORCH_RUNTIME=temporal\n", encoding="utf-8")
    settings = Settings.from_env(dotenv_path=dotenv, korch_runtime="local")
    assert settings.korch_runtime == "local"
