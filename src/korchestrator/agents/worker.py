"""Cognitive layer (L2). Imports: agents, interfaces, models, exceptions, stdlib. dspy is lazy.

``WorkerAgent`` — the default reasoning agent (spec 05 §36, ADR 0013). It compiles its ``Signature``
into a ``dspy.Predict`` at call time, runs it under the **injected** ``IModelGateway`` (MockLM
offline or a real gateway), and folds the reply into a ``StateUpdate``. Two adaptations make
``dspy`` fit the SDK's contracts:

* a ``dspy.LM`` subclass routes DSPy's model calls to :meth:`IModelGateway.complete` instead of
  litellm, so heterogeneous per-agent models and the offline MockLM both work; and
* a lenient chat adapter falls back to the first output field when the model's reply is not
  field-marked, so a deterministic MockLM echo still parses.

The blocking DSPy call runs in a worker thread (``asyncio.to_thread``) so superstep parallelism is
real, and it is confined to that activity boundary — never workflow scope (``determinism.md``).
``dspy`` is imported only inside :meth:`_reason`; a base install raises ``MissingExtraError`` there.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from korchestrator.agents.base import Agent
from korchestrator.agents.signatures import Signature, WorkerSignature, load_dspy
from korchestrator.exceptions import ConfigurationError, ProviderError
from korchestrator.interfaces import IModelGateway
from korchestrator.models.state import AgentState, Message, MessageRole, StateUpdate

__all__ = ["WorkerAgent"]

# Placeholder model used only when neither the agent config nor routing (P5) names one. MockLM
# ignores it; a real gateway requires a real model, i.e. set AgentConfig.model until routing lands.
_PLACEHOLDER_MODEL = "korch-default"

# Fixed timestamp for the transient messages handed to the gateway; the gateway ignores valid_time
# and this keeps reasoning from advancing the injected clock (which stamps the real StateUpdate).
_PROMPT_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Bound on the rendered conversation context handed to the model.
_MAX_CONTEXT_MESSAGES = 20


class WorkerAgent(Agent):
    """A reasoning :class:`~korchestrator.agents.Agent` driven by a compiled DSPy signature.

    Construct it like any agent; the composition root binds the clock and model gateway
    (``bind(clock=..., gateway=...)``). :meth:`think` compiles the signature, runs it under the
    gateway, and returns a :class:`StateUpdate` whose message carries the model's answer and whose
    ``halt`` reflects the signature's ``is_final`` output.

    Requires the ``[dspy]`` extra: reasoning raises an actionable ``MissingExtraError`` on a base
    install (ADR 0013). Under MockLM it is fully offline and deterministic.

    Args:
        id: The agent identifier (see :class:`Agent`).
        role: The persona role.
        signature: The reasoning :class:`~korchestrator.agents.signatures.Signature`; defaults to
            :class:`~korchestrator.agents.signatures.WorkerSignature`.
        model: The model to route to, or ``None`` to let routing (P5) decide.
        goal, backstory, tools, max_react_steps, hitl_threshold, timeout_seconds: As for
            :class:`Agent`.

    Example:
        >>> from korchestrator.agents.worker import WorkerAgent
        >>> agent = WorkerAgent(id="analyst", role="analyst")  # doctest: +SKIP
    """

    def __init__(
        self,
        id: str,  # noqa: A002 — public field name matches AgentConfig (spec 04)
        *,
        role: str,
        signature: type[Signature] = WorkerSignature,
        model: str | None = None,
        goal: str = "",
        backstory: str = "",
        tools: tuple[str, ...] = (),
        max_react_steps: int = 3,
        hitl_threshold: float | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        """Build the agent config and record the reasoning signature."""
        super().__init__(
            id,
            role=role,
            model=model,
            goal=goal,
            backstory=backstory,
            tools=tools,
            max_react_steps=max_react_steps,
            hitl_threshold=hitl_threshold,
            timeout_seconds=timeout_seconds,
        )
        self._signature = signature

    async def think(self, state: AgentState) -> StateUpdate:
        """Reason about ``state`` under the injected gateway and return a :class:`StateUpdate`.

        The blocking DSPy call runs in a worker thread so a superstep's agents run concurrently.

        Args:
            state: The frozen state snapshot. Never mutated.

        Returns:
            A :class:`StateUpdate` with one assistant :class:`Message` (the answer) and ``halt`` set
            from the reasoning's ``is_final`` signal.

        Raises:
            MissingExtraError: If the ``[dspy]`` extra is not installed.
            ConfigurationError: If no model gateway has been bound.
            ProviderError: If the underlying reasoning call fails.
        """
        answer, is_final = await asyncio.to_thread(self._reason, state)
        now = self.clock.now()
        message = Message(
            id=f"{state.run_id}:{state.superstep}:{self.id}:0",
            role=MessageRole.ASSISTANT,
            kind="answer" if is_final else "thought",
            sender=self.id,
            content=answer,
            superstep=state.superstep,
            valid_time=now,
        )
        return StateUpdate(agent_id=self.id, messages=(message,), halt=is_final, valid_time=now)

    def _reason(self, state: AgentState) -> tuple[str, bool]:
        """Compile the signature and run it under the gateway (synchronous; called via a thread)."""
        gateway = self._require_gateway()
        dspy = load_dspy()
        model = self.config.model or _PLACEHOLDER_MODEL
        compiled = self._signature.to_dspy()
        lm = _build_gateway_lm(dspy, gateway, model)
        adapter = _build_lenient_adapter(dspy)
        predictor = dspy.Predict(compiled)
        inputs = self._build_inputs(state)
        try:
            with dspy.context(lm=lm, adapter=adapter):
                result = predictor(**inputs)
        except Exception as exc:
            raise ProviderError(
                f"Worker {self.id!r} reasoning failed: {exc}. Check the model gateway and the "
                "signature.",
                agent_id=self.id,
            ) from exc
        answer = str(getattr(result, self._answer_field(), ""))
        is_final = bool(getattr(result, "is_final", False))
        return answer, is_final

    def _require_gateway(self) -> IModelGateway:
        if self._gateway is None:
            raise ConfigurationError(
                f"WorkerAgent {self.id!r} has no model gateway bound. Call "
                "bind(clock=..., gateway=...) before running (the composition root does this)."
            )
        return self._gateway

    def _build_inputs(self, state: AgentState) -> dict[str, str]:
        known = {
            "role": self.persona.role or self.id,
            "objective": state.objective,
            "context": _render_context(state),
        }
        return {
            name: known.get(name, state.objective)
            for name, _, spec in self._signature.fields()
            if spec.kind == "input"
        }

    def _answer_field(self) -> str:
        for name, _, spec in self._signature.fields():
            if spec.kind == "output":
                return name
        return "answer"


def _render_context(state: AgentState) -> str:
    """Render the recent conversation as plain text for the model prompt."""
    recent = state.messages[-_MAX_CONTEXT_MESSAGES:]
    if not recent:
        return "(no prior messages)"
    return "\n".join(f"{message.sender}: {message.content}" for message in recent)


def _build_gateway_lm(dspy: Any, gateway: IModelGateway, model: str) -> Any:
    """Build a ``dspy.LM`` that routes DSPy's calls to ``gateway`` instead of litellm."""

    class _GatewayLM(dspy.LM):  # type: ignore[misc]  # dspy (optional extra) is typed Any
        def __init__(self) -> None:
            super().__init__(model=f"korch/{model}", cache=False, num_retries=0)

        def __call__(
            self,
            prompt: str | None = None,
            messages: list[dict[str, Any]] | None = None,
            **kwargs: Any,
        ) -> list[str]:
            reply = asyncio.run(gateway.complete(_to_messages(prompt, messages), model=model))
            return [reply.content]

    lm: Any = _GatewayLM()
    return lm


def _build_lenient_adapter(dspy: Any) -> Any:
    """Build a chat adapter that tolerates a non-field-marked reply (e.g. a MockLM echo)."""

    class _LenientChatAdapter(dspy.ChatAdapter):  # type: ignore[misc]  # dspy is typed Any
        def parse(self, signature: Any, completion: str) -> dict[str, Any]:
            try:
                return super().parse(signature, completion)  # type: ignore[no-any-return]
            except Exception:
                return _fallback_fields(signature, completion)

    adapter: Any = _LenientChatAdapter()
    return adapter


def _fallback_fields(signature: Any, completion: str) -> dict[str, Any]:
    """Assign a plain completion to the first output field; default the rest by type."""
    result: dict[str, Any] = {}
    for index, (name, field) in enumerate(signature.output_fields.items()):
        if field.annotation is bool:
            result[name] = False
        elif index == 0:
            result[name] = completion.strip()
        else:
            result[name] = ""
    return result


def _to_messages(prompt: str | None, messages: list[dict[str, Any]] | None) -> list[Message]:
    """Convert DSPy's chat messages (or a bare prompt) into gateway :class:`Message`s."""
    raw = messages if messages is not None else [{"role": "user", "content": prompt or ""}]
    converted: list[Message] = []
    for index, item in enumerate(raw):
        role = str(item.get("role", "user"))
        converted.append(
            Message(
                id=f"dspy:{index}",
                role=_ROLE_MAP.get(role, MessageRole.USER),
                sender=role,
                content=str(item.get("content", "")),
                superstep=0,
                valid_time=_PROMPT_TIME,
            )
        )
    return converted


_ROLE_MAP = {
    "system": MessageRole.SYSTEM,
    "user": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "tool": MessageRole.TOOL,
}
