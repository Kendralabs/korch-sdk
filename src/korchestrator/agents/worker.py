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

When ``AgentConfig.tools`` is non-empty, reasoning runs a bounded ReAct loop instead of a single
predict call (P10.2, closing the gap P4.6/P6 left open — see ADR 0018): each step lets the model
either call one mounted tool (via the injected ``IToolInvoker``, never ``tools/`` directly — spec
05's allowed-imports table for ``agents/`` does not list it) or answer, bounded by
``max_react_steps``. Each tool call is recorded as its own ``kind="tool"`` message alongside the
final ``kind="answer"``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from korchestrator.agents._reasoning import PLACEHOLDER_MODEL, predict_under_gateway
from korchestrator.agents.base import Agent
from korchestrator.agents.signatures import (
    ReActWorkerSignature,
    Signature,
    WorkerSignature,
    load_dspy,
)
from korchestrator.exceptions import ConfigurationError, ProviderError
from korchestrator.interfaces import IModelGateway, IToolInvoker
from korchestrator.models.state import AgentState, Message, MessageRole, StateUpdate
from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["WorkerAgent"]

# Bound on the rendered conversation context handed to the model.
_MAX_CONTEXT_MESSAGES = 20


@dataclass(frozen=True)
class _Outcome:
    """One ``_reason`` result: any tool-call observations, then the final answer."""

    tool_steps: tuple[str, ...] = field(default_factory=tuple)
    answer: str = ""
    is_final: bool = False


class WorkerAgent(Agent):
    """A reasoning :class:`~korchestrator.agents.Agent` driven by a compiled DSPy signature.

    Construct it like any agent; the composition root binds the clock, model gateway, and (when
    tools are mounted) the tool invoker (``bind(clock=..., gateway=..., tool_invoker=...)``).
    :meth:`think` compiles the signature, runs it under the gateway, and returns a
    :class:`StateUpdate` whose message carries the model's answer and whose ``halt`` reflects the
    signature's ``is_final`` output.

    Requires the ``[dspy]`` extra: reasoning raises an actionable ``MissingExtraError`` on a base
    install (ADR 0013). Under MockLM it is fully offline and deterministic.

    Args:
        id: The agent identifier (see :class:`Agent`).
        role: The persona role.
        signature: The reasoning :class:`~korchestrator.agents.signatures.Signature`; defaults to
            :class:`~korchestrator.agents.signatures.WorkerSignature`. Ignored when ``tools`` is
            non-empty — the built-in ReAct signature is used instead (it needs specific fields).
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

        The blocking DSPy call(s) run in a worker thread so a superstep's agents run concurrently.

        Args:
            state: The frozen state snapshot. Never mutated.

        Returns:
            A :class:`StateUpdate`: one ``kind="tool"`` message per tool call this turn (if any),
            then one ``kind="answer"`` message. ``halt`` is set from the reasoning's ``is_final``.

        Raises:
            MissingExtraError: If the ``[dspy]`` extra is not installed.
            ConfigurationError: If no model gateway is bound, or ``tools`` is mounted with no
                tool invoker bound.
            ProviderError: If the underlying reasoning call fails.
        """
        outcome = await asyncio.to_thread(self._reason, state)
        messages = []
        for index, step in enumerate(outcome.tool_steps):
            messages.append(
                Message(
                    id=f"{state.run_id}:{state.superstep}:{self.id}:{index}",
                    role=MessageRole.ASSISTANT,
                    kind="tool",
                    sender=self.id,
                    content=step,
                    superstep=state.superstep,
                    valid_time=self.clock.now(),
                )
            )
        now = self.clock.now()
        messages.append(
            Message(
                id=f"{state.run_id}:{state.superstep}:{self.id}:{len(outcome.tool_steps)}",
                role=MessageRole.ASSISTANT,
                kind="answer",
                sender=self.id,
                content=outcome.answer,
                superstep=state.superstep,
                valid_time=now,
            )
        )
        return StateUpdate(
            agent_id=self.id, messages=tuple(messages), halt=outcome.is_final, valid_time=now
        )

    def _reason(self, state: AgentState) -> _Outcome:
        """Compile the signature and run it under the gateway (synchronous; called via a thread)."""
        gateway = self._require_gateway()
        # load_dspy is outside the try so MissingExtraError propagates past the wrap (ADR 0013).
        dspy = load_dspy()
        model = self.config.model or PLACEHOLDER_MODEL
        if not self.config.tools:
            return self._reason_single(dspy, gateway, model, state)
        return self._reason_with_tools(dspy, gateway, model, state)

    def _reason_single(
        self, dspy: Any, gateway: IModelGateway, model: str, state: AgentState
    ) -> _Outcome:
        """The original, unchanged single-predict path for an agent with no tools mounted."""
        result = self._predict(dspy, self._signature, gateway, model, self._build_inputs(state))
        answer = str(getattr(result, self._answer_field(), ""))
        is_final = bool(getattr(result, "is_final", False))
        return _Outcome(answer=answer, is_final=is_final)

    def _reason_with_tools(
        self, dspy: Any, gateway: IModelGateway, model: str, state: AgentState
    ) -> _Outcome:
        """Bounded ReAct loop: predict, optionally call a tool, feed the result back, repeat."""
        invoker = self._require_tool_invoker()
        scratchpad: list[str] = []
        tool_steps: list[str] = []
        answer = ""
        is_final = False
        for _step in range(max(self.config.max_react_steps, 1)):
            inputs = self._build_react_inputs(state, scratchpad)
            result = self._predict(dspy, ReActWorkerSignature, gateway, model, inputs)
            answer = str(getattr(result, "answer", ""))
            is_final = bool(getattr(result, "is_final", False))
            tool_name = str(getattr(result, "tool_name", "")).strip()
            if not tool_name:
                return _Outcome(tool_steps=tuple(tool_steps), answer=answer, is_final=is_final)
            raw_args = str(getattr(result, "tool_args", ""))
            observation = self._call_tool(invoker, state, tool_name, raw_args)
            scratchpad.append(observation)
            tool_steps.append(observation)
        # max_react_steps exhausted without a final answer: degrade to the last reply, not halted.
        return _Outcome(tool_steps=tuple(tool_steps), answer=answer, is_final=False)

    def _call_tool(
        self, invoker: IToolInvoker, state: AgentState, tool_name: str, raw_args: str
    ) -> str:
        """Parse ``raw_args`` and invoke ``tool_name``, returning a one-line observation."""
        args = _parse_tool_args(raw_args)
        if args is None:
            return f"[error] tool_args for {tool_name!r} was not a valid JSON object: {raw_args!r}"
        result = asyncio.run(
            invoker.invoke_tool(
                tool_name, args, tenant_id=state.tenant_id, mounted=set(self.config.tools)
            )
        )
        return _format_observation(tool_name, args, result)

    def _predict(
        self,
        dspy: Any,
        signature_cls: type[Signature],
        gateway: IModelGateway,
        model: str,
        inputs: dict[str, str],
    ) -> Any:
        try:
            return predict_under_gateway(
                dspy, signature_cls, gateway=gateway, model=model, inputs=inputs
            )
        except Exception as exc:
            raise ProviderError(
                f"Worker {self.id!r} reasoning failed: {exc}. Check the model gateway and the "
                "signature.",
                agent_id=self.id,
            ) from exc

    def _require_gateway(self) -> IModelGateway:
        if self._gateway is None:
            raise ConfigurationError(
                f"WorkerAgent {self.id!r} has no model gateway bound. Call "
                "bind(clock=..., gateway=...) before running (the composition root does this)."
            )
        return self._gateway

    def _require_tool_invoker(self) -> IToolInvoker:
        if self._tool_invoker is None:
            raise ConfigurationError(
                f"WorkerAgent {self.id!r} mounts tools={self.config.tools!r} but no tool invoker "
                "is bound. Pass connectors=[...] to Korch/Swarm — the composition root binds it."
            )
        return self._tool_invoker

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

    def _build_react_inputs(self, state: AgentState, scratchpad: list[str]) -> dict[str, str]:
        context = _render_context(state)
        if scratchpad:
            context = f"{context}\n" + "\n".join(scratchpad)
        invoker = self._tool_invoker
        tools_desc = "\n".join(
            f"{name}: {invoker.describe_tool(name) if invoker is not None else ''}"
            for name in self.config.tools
        )
        return {
            "role": self.persona.role or self.id,
            "objective": state.objective,
            "context": context,
            "available_tools": tools_desc or "(none)",
        }

    def _answer_field(self) -> str:
        for name, _, spec in self._signature.fields():
            if spec.kind == "output":
                return name
        return "answer"


def _parse_tool_args(raw: str) -> dict[str, JSONValue] | None:
    """Parse a ReAct step's ``tool_args`` output as a JSON object; ``None`` on any mismatch.

    An empty string means "no arguments", not an error. Model output is untrusted input (spec 08
    §5) — this only ever calls ``json.loads``, never ``eval``, and a parse failure is fed back to
    the model as an observation rather than raised, so the loop can self-correct.
    """
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _format_observation(tool_name: str, args: Mapping[str, JSONValue], result: ToolResult) -> str:
    """Render one tool call and its result as a single line for the next ReAct step's context."""
    if result.ok:
        return f"tool {tool_name}({args}) -> {result.output!r}"
    return f"tool {tool_name}({args}) failed ({result.error_code}): {result.error}"


def _render_context(state: AgentState) -> str:
    """Render the recent conversation as plain text for the model prompt."""
    recent = state.messages[-_MAX_CONTEXT_MESSAGES:]
    if not recent:
        return "(no prior messages)"
    return "\n".join(f"{message.sender}: {message.content}" for message in recent)
