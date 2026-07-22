"""Unit tests for a2a directed messaging and the handoff transformer (P6.5)."""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.a2a import HandoffTransformer, directed_message
from korchestrator.models.state import Performative

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_directed_message_addresses_the_recipient() -> None:
    msg = directed_message(sender="a", recipient="b", content="hi", superstep=0, valid_time=NOW)
    assert msg.recipient == "b"
    assert msg.sender == "a"
    assert msg.performative is Performative.INFORM


def test_handoff_is_a_request_addressed_to_the_target() -> None:
    handoff = HandoffTransformer().transform(
        sender="researcher", recipient="writer", content="findings", superstep=1, valid_time=NOW
    )
    assert handoff.kind == "handoff"
    assert handoff.recipient == "writer"
    assert handoff.performative is Performative.REQUEST
    assert handoff.content == "findings"


def test_handoff_prefixes_the_summary() -> None:
    handoff = HandoffTransformer().transform(
        sender="a",
        recipient="b",
        content="the data",
        superstep=0,
        valid_time=NOW,
        summary="Please summarize",
    )
    assert handoff.content == "Please summarize\n\nthe data"
