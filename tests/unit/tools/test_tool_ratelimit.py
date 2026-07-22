"""Unit tests for the token-bucket rate limiter (P6.2)."""

from __future__ import annotations

import pytest

from korchestrator.tools._ratelimit import RateLimiter, TokenBucketRateLimiter


def test_burst_then_empty_then_refill() -> None:
    now = [0.0]
    limiter = TokenBucketRateLimiter(capacity=2, refill_per_second=1.0, time_source=lambda: now[0])
    assert [limiter.allow("t"), limiter.allow("t"), limiter.allow("t")] == [True, True, False]
    now[0] = 1.0  # one token refilled
    assert limiter.allow("t") is True
    assert limiter.allow("t") is False


def test_keys_have_independent_buckets() -> None:
    now = [0.0]
    limiter = TokenBucketRateLimiter(capacity=1, refill_per_second=1.0, time_source=lambda: now[0])
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True  # separate bucket, not exhausted by "a"
    assert limiter.allow("a") is False


def test_is_a_rate_limiter() -> None:
    assert isinstance(TokenBucketRateLimiter(capacity=1, refill_per_second=1.0), RateLimiter)


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(capacity=0, refill_per_second=1.0)
