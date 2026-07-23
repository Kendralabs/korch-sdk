"""Unit tests for configure()/get_settings() (spec 08 §1.2, ADR 0016).

Every test uses the ``settings`` fixture (``tests/conftest.py``), which resets the process-wide
installed instance before and after the test, and passes ``dotenv_path=None`` explicitly unless a
test is specifically exercising ``configure()``'s ``.env`` default — no ambient developer ``.env``
can affect these tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from korchestrator.config import Settings, configure, get_settings
from korchestrator.exceptions import ValidationError as KorchValidationError

pytestmark = pytest.mark.usefixtures("settings")

_ENV_VARS = ("KORCH_RUNTIME",)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_get_settings_builds_the_zero_config_default_on_first_call() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.korch_runtime == "local"


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_configure_installs_a_new_settings_and_returns_it() -> None:
    installed = configure(dotenv_path=None, korch_runtime="temporal")
    assert installed.korch_runtime == "temporal"
    assert get_settings() is installed


def test_configure_overrides_a_previously_installed_settings() -> None:
    configure(dotenv_path=None, korch_runtime="temporal")
    configure(dotenv_path=None, korch_runtime="local")
    assert get_settings().korch_runtime == "local"


def test_configure_wraps_a_structural_failure_into_korch_validation_error() -> None:
    with pytest.raises(KorchValidationError) as info:
        configure(dotenv_path=None, korch_runtime="not-a-real-runtime")
    assert info.value.code == "KORCH_VALIDATION_FAILED"
    assert info.value.__cause__ is not None


def test_a_failed_configure_call_does_not_change_the_installed_settings() -> None:
    configure(dotenv_path=None, korch_runtime="temporal")
    with pytest.raises(KorchValidationError):
        configure(dotenv_path=None, korch_runtime="not-a-real-runtime")
    assert get_settings().korch_runtime == "temporal"


def test_configure_reads_dotenv_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("KORCH_RUNTIME=temporal\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert configure().korch_runtime == "temporal"


def test_configure_dotenv_path_none_skips_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("KORCH_RUNTIME=temporal\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert configure(dotenv_path=None).korch_runtime == "local"
