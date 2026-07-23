"""Shared test configuration and fixtures.

Registers a Hypothesis profile so property-based tests are deterministic and robust on slow
machines: a bounded example count, no per-example deadline (wall-clock timing must never decide a
test — spec 09 §3), and the input-generation speed health check suppressed. Also exposes the shared
test doubles from ``tests/fixtures/`` (pytest puts this conftest's directory on ``sys.path``, so the
``fixtures`` package resolves without any path manipulation — spec 02 §2).
"""

from collections.abc import Callable, Iterator

import pytest

from fixtures.fake_clock import FakeClock

# hypothesis is only needed for the property tests (the [dev] / full job). The base-install,
# [temporal], and [remote] CI jobs install it selectively, so its absence must not break conftest.
# Imported under an alias — `settings` below is this file's own fixture name (spec 08 §1.2).
try:
    from hypothesis import HealthCheck
    from hypothesis import settings as hypothesis_settings
except ImportError:
    pass
else:
    hypothesis_settings.register_profile(
        "korch",
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    hypothesis_settings.load_profile("korch")


@pytest.fixture
def make_clock() -> Callable[..., FakeClock]:
    """Return a factory that builds fresh, deterministic :class:`FakeClock` instances."""
    return FakeClock


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset the process-wide installed ``Settings`` for the test (spec 08 §1.2).

    ``configure()``/``get_settings()`` share one module-level instance; this fixture clears it
    before the test and restores whatever was there afterwards, so no test leaks its `configure()`
    call into another.
    """
    from korchestrator.config import process

    monkeypatch.setattr(process, "_installed", None)
    yield
