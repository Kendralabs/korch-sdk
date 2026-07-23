"""Unit tests for the namespaced korchestrator logger (spec 08 §3, P8.3)."""

from __future__ import annotations

import io
import logging

import pytest

from korchestrator.exceptions import ValidationError
from korchestrator.logging import disable_logging, enable_logging
from korchestrator.logging.logger import _logger


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Ensure no test leaks an attached handler into another."""
    disable_logging()
    yield
    disable_logging()


def test_a_null_handler_is_attached_by_default() -> None:
    handlers = [h for h in _logger.handlers if isinstance(h, logging.NullHandler)]
    assert len(handlers) == 1


def test_off_by_default_no_stream_handler_attached() -> None:
    assert not any(isinstance(h, logging.StreamHandler) for h in _logger.handlers)


def test_enable_logging_attaches_a_stream_handler() -> None:
    stream = io.StringIO()
    enable_logging("DEBUG", stream=stream)
    handlers = [h for h in _logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(handlers) == 1
    assert _logger.level == logging.DEBUG


def test_enable_logging_defaults_to_info() -> None:
    enable_logging(stream=io.StringIO())
    assert _logger.level == logging.INFO


def test_enable_logging_is_idempotent_not_additive() -> None:
    enable_logging("INFO", stream=io.StringIO())
    enable_logging("DEBUG", stream=io.StringIO())
    handlers = [h for h in _logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(handlers) == 1
    assert _logger.level == logging.DEBUG


def test_enable_logging_rejects_an_unrecognised_level() -> None:
    with pytest.raises(ValidationError):
        enable_logging("VERBOSE")


def test_enable_logging_is_case_insensitive() -> None:
    enable_logging("debug", stream=io.StringIO())
    assert _logger.level == logging.DEBUG


def test_disable_logging_removes_the_handler() -> None:
    enable_logging(stream=io.StringIO())
    disable_logging()
    assert not any(isinstance(h, logging.StreamHandler) for h in _logger.handlers)


def test_disable_logging_is_idempotent() -> None:
    disable_logging()
    disable_logging()  # must not raise


def test_enable_logging_never_touches_the_root_logger() -> None:
    # Compare snapshots taken within the test, not against a module-import-time snapshot: test
    # runners (pytest's own log capture) legitimately attach their own handlers to root between
    # tests, which is not something enable_logging() controls or should be judged against.
    handlers_before = list(logging.root.handlers)
    level_before = logging.root.level
    enable_logging("DEBUG", stream=io.StringIO())
    assert logging.root.handlers == handlers_before
    assert logging.root.level == level_before


def test_a_message_reaches_the_stream_once_enabled() -> None:
    stream = io.StringIO()
    enable_logging("INFO", stream=stream)
    logging.getLogger("korchestrator.test").warning("something degraded")
    assert "something degraded" in stream.getvalue()


def test_a_message_does_not_reach_a_stale_stream_after_re_enabling() -> None:
    first_stream = io.StringIO()
    enable_logging("INFO", stream=first_stream)
    second_stream = io.StringIO()
    enable_logging("INFO", stream=second_stream)
    logging.getLogger("korchestrator.test").warning("routed to the new stream")
    assert "routed to the new stream" not in first_stream.getvalue()
    assert "routed to the new stream" in second_stream.getvalue()
