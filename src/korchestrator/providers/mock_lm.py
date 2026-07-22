"""Adapter layer. Imports: korchestrator.models, stdlib. No network, no optional dependency.

The deterministic offline ``MockLM`` gateway — the default ``IModelGateway`` (spec 03 §4). The same
messages always yield the same completion; it supports scripted per-model responses and records a
call log for assertions. It is what makes the full agent path testable in CI with no network and no
credentials (spec 09 §3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from korchestrator.models.routing import ModelCard
from korchestrator.models.state import Message, MessageRole

__all__ = ["MockCall", "MockLM"]

# A fixed, deterministic timestamp for mock completions. The agent layer stamps the real
# ``valid_time`` from the injected clock when it builds its StateUpdate; this is only a placeholder.
_MOCK_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

_MOCK_MODEL_CARD = ModelCard(
    name="mock-model",
    provider="mock",
    description="Deterministic offline mock model for tests and zero-config runs.",
    context_window=8192,
    cost_per_1k_input_usd=0.0,
    cost_per_1k_output_usd=0.0,
    latency_p50_ms=0,
    quality_score=1.0,
)


@dataclass(frozen=True)
class MockCall:
    """One recorded call to :meth:`MockLM.complete`, for test assertions."""

    model: str
    messages: tuple[Message, ...]


class MockLM:
    """A deterministic, offline model gateway (the default ``IModelGateway``).

    Completions are deterministic: a scripted response for the model if one is registered, otherwise
    a canned echo of the latest message content. No network, no randomness, no credentials.

    Args:
        responses: Scripted completions keyed by model name; a matched model returns its scripted
            text verbatim.
        default_response: The completion for any unscripted model. Defaults to an echo of the
            prompt's last message.
        seed: Accepted for API symmetry with real gateways; the mock is fully deterministic and does
            not use it to introduce randomness.

    Example:
        >>> import asyncio
        >>> from korchestrator.providers import MockLM
        >>> from korchestrator.models.state import Message
        >>> gateway = MockLM(responses={"gpt-4o-mini": "the summary"})
        >>> msg = Message(id="m", sender="user", content="Summarize", superstep=0,
        ...               valid_time=__import__("datetime").datetime(2026, 1, 1))
        >>> asyncio.run(gateway.complete([msg], model="gpt-4o-mini")).content
        'the summary'
    """

    def __init__(
        self,
        *,
        responses: Mapping[str, str] | None = None,
        default_response: str | None = None,
        seed: int = 0,
    ) -> None:
        """Store the scripted responses, the default, and the (unused-for-randomness) seed."""
        self._responses = dict(responses or {})
        self._default = default_response
        self._seed = seed
        self._calls: list[MockCall] = []

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        max_tokens: int | None = None,
    ) -> Message:
        """Return a deterministic completion and record the call.

        Args:
            messages: The conversation so far; the last message's content seeds the echo.
            model: The model name; a scripted response for it wins over the default.
            max_tokens: Accepted for gateway parity; ignored by the mock.

        Returns:
            An assistant :class:`Message` with the deterministic completion.
        """
        self._calls.append(MockCall(model=model, messages=tuple(messages)))
        content = self._response_for(model, messages)
        return Message(
            id="mock",
            role=MessageRole.ASSISTANT,
            content=content,
            sender="assistant",
            superstep=0,
            valid_time=_MOCK_TIME,
        )

    async def available_models(self) -> list[ModelCard]:
        """Return the single mock model card."""
        return [_MOCK_MODEL_CARD]

    @property
    def calls(self) -> tuple[MockCall, ...]:
        """The recorded call log, in call order."""
        return tuple(self._calls)

    def _response_for(self, model: str, messages: Sequence[Message]) -> str:
        if model in self._responses:
            return self._responses[model]
        if self._default is not None:
            return self._default
        last = messages[-1].content if messages else ""
        return f"[mock:{model}] {last[:120]}"
