"""Context layer. Imports: models, exceptions, stdlib.

The Context Compiler and Minimum Viable Context (MVC) extraction. Given an :class:`AgentState`
snapshot, :meth:`ContextCompiler.compile` builds the smallest useful prompt context under a budget:
it keeps the objective and the substantive messages (answers, handoffs) first, packs in the most
recent remainder, and prunes the rest. An optional summariser folds the pruned tail into a short
note; if none is given (or it fails) the compiler degrades gracefully to a count.

This runs **off the hot loop** — an agent calls it against a frozen snapshot; it never mutates state
and, without a summariser, is pure and deterministic (safe to call anywhere).
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.models.state import AgentState, Message

__all__ = ["CompiledContext", "ContextCompiler", "Summarizer"]

# Turns the pruned-message text into a short summary. May do I/O (a model call); the compiler
# isolates its failures, so a broken summariser never breaks compilation.
Summarizer = Callable[[str], str]

# Relative value of each message kind when the budget forces a choice.
_PRIORITY: dict[str, int] = {"answer": 3, "handoff": 2, "tool": 1, "thought": 0}


class CompiledContext(BaseModel):
    """The compiled, budget-bounded context for one reasoning step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    message_ids: tuple[str, ...] = ()
    original_count: int = Field(ge=0)
    included_count: int = Field(ge=0)
    pruned_count: int = Field(ge=0)
    truncated: bool = False
    summarized: bool = False


class ContextCompiler:
    """Compile an :class:`AgentState` into a Minimum Viable Context under a budget.

    Args:
        max_messages: Hard cap on how many messages to include.
        max_chars: Character budget for the rendered message body (the objective header is always
            kept). A proxy for tokens — deterministic and dependency-free.
        summarizer: Optional callable that summarises the pruned tail; failures degrade to a count.

    Example:
        >>> from datetime import datetime, timezone
        >>> from korchestrator.models.state import AgentState, Message
        >>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        >>> msgs = tuple(
        ...     Message(id=str(i), sender="a", content=f"m{i}", superstep=0, valid_time=now)
        ...     for i in range(100)
        ... )
        >>> state = AgentState(
        ...     run_id="r", objective="Summarize the incident", messages=msgs, transaction_time=now
        ... )
        >>> compiled = ContextCompiler(max_chars=50).compile(state)
        >>> compiled.included_count < compiled.original_count
        True
    """

    def __init__(
        self,
        *,
        max_messages: int = 20,
        max_chars: int = 4000,
        summarizer: Summarizer | None = None,
    ) -> None:
        """Store the MVC budget and the optional summariser."""
        self._max_messages = max_messages
        self._max_chars = max_chars
        self._summarizer = summarizer

    def compile(self, state: AgentState) -> CompiledContext:
        """Extract the Minimum Viable Context for ``state`` and return it, pruning to fit."""
        messages = state.messages
        included = self._select(messages)
        pruned = [m for m in messages if m not in included]

        summary, summarized = self._summarize(pruned)
        body = "\n".join(_render(m) for m in included)
        text = f"Objective: {state.objective}"
        if summary:
            text += f"\n\n{summary}"
        if body:
            text += f"\n\n{body}"

        return CompiledContext(
            text=text,
            message_ids=tuple(m.id for m in included),
            original_count=len(messages),
            included_count=len(included),
            pruned_count=len(pruned),
            truncated=bool(pruned),
            summarized=summarized,
        )

    def _select(self, messages: tuple[Message, ...]) -> list[Message]:
        """Pick messages by priority (answers/handoffs first) then recency, within the budget."""
        # Rank by (kind priority, original index) descending so substantive, recent messages win.
        ranked = sorted(
            enumerate(messages),
            key=lambda item: (_PRIORITY.get(item[1].kind, 0), item[0]),
            reverse=True,
        )
        chosen: set[int] = set()
        used = 0
        for index, message in ranked:
            if len(chosen) >= self._max_messages:
                break
            cost = len(_render(message)) + 1
            if used + cost > self._max_chars:
                continue
            chosen.add(index)
            used += cost
        return [messages[i] for i in sorted(chosen)]  # restore chronological order

    def _summarize(self, pruned: list[Message]) -> tuple[str, bool]:
        if not pruned:
            return "", False
        if self._summarizer is None:
            return f"[{len(pruned)} earlier message(s) omitted to fit the context budget]", False
        try:
            summary = self._summarizer("\n".join(_render(m) for m in pruned))
        except Exception:
            # Degrade gracefully: a broken summariser must never break compilation.
            return f"[{len(pruned)} earlier message(s) omitted to fit the context budget]", False
        return f"[summary of {len(pruned)} earlier message(s): {summary}]", True


def _render(message: Message) -> str:
    return f"{message.sender}: {message.content}"
