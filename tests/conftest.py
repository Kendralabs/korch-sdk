"""Shared test configuration and fixtures.

Registers a Hypothesis profile so property-based tests are deterministic and robust on slow
machines: a bounded example count, no per-example deadline (wall-clock timing must never decide a
test — spec 09 §3), and the input-generation speed health check suppressed. Also exposes the shared
test doubles from ``tests/fixtures/`` (pytest puts this conftest's directory on ``sys.path``, so the
``fixtures`` package resolves without any path manipulation — spec 02 §2).
"""

from collections.abc import Callable

import pytest
from hypothesis import HealthCheck, settings

from fixtures.fake_clock import FakeClock

settings.register_profile(
    "korch",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("korch")


@pytest.fixture
def make_clock() -> Callable[..., FakeClock]:
    """Return a factory that builds fresh, deterministic :class:`FakeClock` instances."""
    return FakeClock
