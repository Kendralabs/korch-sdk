"""Integration layer (L4). Imports: stdlib.

A small token-bucket rate limiter for the AUB bridge. Per-key (per-tool) buckets refill at a fixed
rate; :meth:`TokenBucketRateLimiter.allow` consumes a token or reports the limit hit. The time
source is injected (``time.monotonic`` by default) so tests are deterministic without sleeping —
this runs at the activity boundary, never workflow scope.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

__all__ = ["RateLimiter", "TokenBucketRateLimiter"]


@runtime_checkable
class RateLimiter(Protocol):
    """Decide whether a call keyed by ``key`` may proceed now."""

    def allow(self, key: str) -> bool:
        """Return ``True`` and consume budget if the call is within the limit, else ``False``."""
        ...


class TokenBucketRateLimiter:
    """A per-key token bucket: ``capacity`` tokens, refilling at ``refill_per_second``.

    Args:
        capacity: Maximum burst — tokens a fresh key starts with. Must be positive.
        refill_per_second: Steady-state tokens added per second.
        time_source: Monotonic seconds source; injected for deterministic tests.

    Example:
        >>> now = [0.0]
        >>> limiter = TokenBucketRateLimiter(
        ...     capacity=2, refill_per_second=1.0, time_source=lambda: now[0]
        ... )
        >>> [limiter.allow("t"), limiter.allow("t"), limiter.allow("t")]  # burst of 2, then empty
        [True, True, False]
        >>> now[0] = 1.0  # one second later, one token refilled
        >>> limiter.allow("t")
        True
    """

    def __init__(
        self,
        *,
        capacity: int,
        refill_per_second: float,
        time_source: Callable[[], float] | None = None,
    ) -> None:
        """Configure the bucket; default the time source to ``time.monotonic``."""
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        import time

        self._capacity = float(capacity)
        self._refill = float(refill_per_second)
        self._time = time_source or time.monotonic
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill_time)

    def allow(self, key: str) -> bool:
        """Consume a token for ``key`` if available; otherwise report the limit hit."""
        now = self._time()
        tokens, last = self._buckets.get(key, (self._capacity, now))
        tokens = min(self._capacity, tokens + (now - last) * self._refill)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1.0, now)
        return True
