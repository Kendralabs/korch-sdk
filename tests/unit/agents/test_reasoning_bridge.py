"""Unit tests for the DSPy gateway bridge helpers (dspy 3.5 engine contract)."""

from __future__ import annotations

from types import SimpleNamespace

from korchestrator.agents._reasoning import _parts_text, _request_messages, _takes_engine


def _text(value: str) -> SimpleNamespace:
    return SimpleNamespace(text=value)


def test_parts_text_joins_text_and_skips_parts_without_text() -> None:
    parts = (_text("hello "), SimpleNamespace(value={"k": 1}), _text("world"))

    assert _parts_text(parts) == "hello world"


def test_parts_text_passes_a_plain_string_through() -> None:
    assert _parts_text("as is") == "as is"


def test_request_messages_puts_the_system_prompt_first() -> None:
    request = SimpleNamespace(
        system="be brief",
        messages=(
            SimpleNamespace(role="user", parts=(_text("hi"),)),
            SimpleNamespace(role="assistant", parts=(_text("hello"),)),
        ),
    )

    assert _request_messages(request) == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_request_messages_without_a_system_prompt_has_only_the_messages() -> None:
    request = SimpleNamespace(
        system=None, messages=(SimpleNamespace(role="user", parts=(_text("hi"),)),)
    )

    assert _request_messages(request) == [{"role": "user", "content": "hi"}]


def test_takes_engine_follows_the_base_lm_signature_not_the_version() -> None:
    new = SimpleNamespace(BaseLM=type("B", (), {"__init__": lambda self, model, engine=None: None}))
    old = SimpleNamespace(BaseLM=type("B", (), {"__init__": lambda self, model: None}))

    assert _takes_engine(new) is True
    assert _takes_engine(old) is False
