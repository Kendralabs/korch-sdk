"""Unit tests for the context compiler and MVC extraction (P6.6)."""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.context import CompiledContext, ContextCompiler
from korchestrator.models.state import AgentState, Message

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _msg(i: int, *, kind: str = "thought", content: str | None = None) -> Message:
    return Message(
        id=str(i),
        sender="agent",
        kind=kind,  # type: ignore[arg-type]
        content=content if content is not None else f"message number {i}",
        superstep=0,
        valid_time=NOW,
    )


def _state(messages: tuple[Message, ...]) -> AgentState:
    return AgentState(
        run_id="r1",
        objective="Summarize the incident report",
        messages=messages,
        transaction_time=NOW,
    )


def test_compile_keeps_the_objective_and_returns_typed() -> None:
    compiled = ContextCompiler().compile(_state(()))
    assert isinstance(compiled, CompiledContext)
    assert "Summarize the incident report" in compiled.text
    assert compiled.original_count == 0


def test_mvc_reduces_context_size_under_budget() -> None:
    messages = tuple(_msg(i) for i in range(100))
    compiled = ContextCompiler(max_chars=60).compile(_state(messages))
    assert compiled.included_count < compiled.original_count
    assert compiled.pruned_count > 0
    assert compiled.truncated is True
    assert len(compiled.message_ids) == compiled.included_count


def test_answers_are_prioritised_over_thoughts() -> None:
    messages = (
        *(_msg(i) for i in range(10)),  # thoughts
        _msg(99, kind="answer", content="THE ANSWER"),
    )
    compiled = ContextCompiler(max_chars=40).compile(_state(messages))
    assert "THE ANSWER" in compiled.text  # the answer survives pruning


def test_included_messages_are_in_chronological_order() -> None:
    messages = tuple(_msg(i, content=f"c{i}") for i in range(5))
    compiled = ContextCompiler().compile(_state(messages))
    assert compiled.message_ids == ("0", "1", "2", "3", "4")


def test_summarizer_folds_the_pruned_tail() -> None:
    messages = tuple(_msg(i) for i in range(50))
    compiled = ContextCompiler(max_chars=40, summarizer=lambda text: "condensed").compile(
        _state(messages)
    )
    assert compiled.summarized is True
    assert "condensed" in compiled.text


def test_broken_summarizer_degrades_gracefully() -> None:
    def boom(text: str) -> str:
        raise RuntimeError("summariser down")

    messages = tuple(_msg(i) for i in range(50))
    compiled = ContextCompiler(max_chars=40, summarizer=boom).compile(_state(messages))
    assert compiled.summarized is False
    assert "omitted" in compiled.text  # fell back to a count, did not raise


def test_compilation_is_deterministic() -> None:
    messages = tuple(_msg(i) for i in range(30))
    compiler = ContextCompiler(max_chars=80)
    assert compiler.compile(_state(messages)) == compiler.compile(_state(messages))
