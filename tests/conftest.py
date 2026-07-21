"""Shared test configuration and fixtures.

Registers a Hypothesis profile so property-based tests are deterministic and robust on slow
machines: a bounded example count, no per-example deadline (wall-clock timing must never decide a
test — spec 09 §3), and the input-generation speed health check suppressed.
"""

from hypothesis import HealthCheck, settings

settings.register_profile(
    "korch",
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("korch")
