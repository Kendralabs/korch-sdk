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

from korchestrator.agents._reasoning import PLACEHOLDER_MODEL, predict_under_gateway
from korchestrator.agents.base import Agent
from korchestrator.agents.signatures import Signature, WorkerSignature, load_dspy
from korchestrator.exceptions import ConfigurationError, ProviderError
from korchestrator.interfaces import IModelGateway
from korchestrator.models.state import AgentState, Message, MessageRole, StateUpdate

__all__ = ["WorkerAgent"]

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
        # A worker's contribution is its answer, so it accumulates into the run's final_answer; a
        # terminal ``is_final`` additionally halts the node. (Intermediate ReAct thoughts — P6 — will
        # be emitted separately as ``kind="thought"``.)
        message = Message(
            id=f"{state.run_id}:{state.superstep}:{self.id}:0",
            role=MessageRole.ASSISTANT,
            kind="answer",
            sender=self.id,
            content=answer,
            superstep=state.superstep,
            valid_time=now,
        )
        return StateUpdate(agent_id=self.id, messages=(message,), halt=is_final, valid_time=now)

    def _reason(self, state: AgentState) -> tuple[str, bool]:
        """Compile the signature and run it under the gateway (synchronous; called via a thread)."""
        gateway = self._require_gateway()
        # load_dspy is outside the try so MissingExtraError propagates past the wrap (ADR 0013).
        dspy = load_dspy()
        model = self.config.model or PLACEHOLDER_MODEL
        try:
            result = predict_under_gateway(
                dspy,
                self._signature,
                gateway=gateway,
                model=model,
                inputs=self._build_inputs(state),
            )
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
