"""Unit tests for the ChannelSchema reducer binding (spec 06 §3, P2.3)."""

from __future__ import annotations

from korchestrator.core import Append, LastValue, MergeDict
from korchestrator.core.channels import ChannelSchema


def test_default_reducer_is_last_value() -> None:
    assert isinstance(ChannelSchema().reducer_for("anything"), LastValue)


def test_a_bound_channel_uses_its_reducer() -> None:
    schema = ChannelSchema({"log": Append()})
    assert isinstance(schema.reducer_for("log"), Append)
    assert isinstance(schema.reducer_for("unbound"), LastValue)
    assert schema.bound_channels == ("log",)


def test_a_custom_default_applies_to_unbound_channels() -> None:
    schema = ChannelSchema(default=MergeDict())
    assert isinstance(schema.reducer_for("anything"), MergeDict)
