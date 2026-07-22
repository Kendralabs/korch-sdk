"""A deterministic, monotone, injectable clock for tests (spec 02 §4).

No test reads the wall clock (spec 09 §3). A fresh ``FakeClock`` with the same start and step
produces an identical timestamp sequence, which is what makes the repeatability tests byte-stable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeClock:
    """A monotone clock that advances by a fixed step on each call."""

    def __init__(self, *, start: datetime = _EPOCH, step_seconds: float = 1.0) -> None:
        self._now = start
        self._step = timedelta(seconds=step_seconds)

    def __call__(self) -> datetime:
        """Return the current time and advance by one step."""
        current = self._now
        self._now += self._step
        return current
