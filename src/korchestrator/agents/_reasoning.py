"""Cognitive layer internal (L2). Imports: agents.signatures, interfaces, models, stdlib. dspy lazy.

The one DSPy↔``IModelGateway`` bridge shared by the reasoning agents (``WorkerAgent``,
``ArchitectAgent``): a ``dspy.LM`` that routes DSPy's calls to :meth:`IModelGateway.complete`, a
lenient chat adapter that tolerates a non-field-marked reply (so a deterministic MockLM echo still
parses), and the predict call under a per-call ``dspy.context``.

``dspy`` is **never imported here** — the caller loads it (``signatures.load_dspy``) and passes the
module in, so the ``MissingExtraError`` boundary stays with the caller and outside its
reasoning-failure ``try`` (ADR 0013). The blocking predict call is expected to run inside
``asyncio.to_thread`` at the call site — never in workflow scope (``determinism.md``).
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any

from korchestrator.agents.signatures import Signature
from korchestrator.interfaces import IModelGateway
from korchestrator.models.state import Message, MessageRole

__all__ = ["PLACEHOLDER_MODEL", "predict_under_gateway"]

# Placeholder model used only when neither the agent config nor routing (P5) names one. MockLM
# ignores it; a real gateway requires a real model, i.e. set AgentConfig.model until routing lands.
PLACEHOLDER_MODEL = "korch-default"

# Fixed timestamp for the transient messages handed to the gateway; the gateway ignores valid_time
# and this keeps reasoning from advancing the injected clock (which stamps the real StateUpdate).
_PROMPT_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

_ROLE_MAP = {
    "system": MessageRole.SYSTEM,
    "user": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "tool": MessageRole.TOOL,
    "developer": MessageRole.SYSTEM,
}


def predict_under_gateway(
    dspy: Any,
    signature_cls: type[Signature],
    *,
    gateway: IModelGateway,
    model: str,
    inputs: dict[str, str],
) -> Any:
    """Compile ``signature_cls`` and run ``dspy.Predict`` over ``inputs`` under ``gateway``.

    Args:
        dspy: The already-loaded ``dspy`` module (the caller owns the ``MissingExtraError`` edge).
        signature_cls: The reasoning :class:`~korchestrator.agents.signatures.Signature`.
        gateway: The model gateway DSPy's calls are routed to.
        model: The model name passed to :meth:`IModelGateway.complete`.
        inputs: The signature's input-field values.

    Returns:
        The DSPy prediction result object (fields read by the caller).
    """
    lm = _build_gateway_lm(dspy, gateway, model)
    adapter = _build_lenient_adapter(dspy)
    predictor = dspy.Predict(signature_cls.to_dspy())
    with dspy.context(lm=lm, adapter=adapter):
        return predictor(**inputs)


def _build_gateway_lm(dspy: Any, gateway: IModelGateway, model: str) -> Any:
    """Build a DSPy LM that routes DSPy's calls to ``gateway`` instead of litellm.

    dspy 3.5 replaced the ``messages=`` call and ``list[str]`` return with an engine contract
    (``complete(Request) -> Response``, lm15 objects), so it gets its own builder; dspy < 3.5
    keeps the original ``__call__`` override.
    """
    if _takes_engine(dspy):
        return _build_gateway_lm_v35(dspy, gateway, model)
    return _build_gateway_lm_legacy(dspy, gateway, model)


def _takes_engine(dspy: Any) -> bool:
    """True when ``dspy.BaseLM`` accepts an ``engine`` (dspy >= 3.5).

    Feature-detected, not version-compared: 3.4 already ships ``dspy.lm15`` but still calls the LM
    the old way, so the presence of that module does not say which contract applies.
    """
    return "engine" in inspect.signature(dspy.BaseLM.__init__).parameters


def _build_gateway_lm_v35(dspy: Any, gateway: IModelGateway, model: str) -> Any:
    """For dspy >= 3.5: a ``BaseLM`` whose engine answers lm15 ``Request``s from ``gateway``."""
    lm15 = dspy.lm15

    class _GatewayEngine:
        def complete(self, request: Any) -> Any:
            messages = _to_messages(None, _request_messages(request))
            reply = asyncio.run(gateway.complete(messages, model=model))
            return lm15.Response(
                id=None,
                model=f"korch/{model}",
                message=lm15.Message(role="assistant", parts=(lm15.TextPart(text=reply.content),)),
                finish_reason="stop",
                usage=lm15.Usage(),
            )

    class _GatewayLM(dspy.BaseLM):  # type: ignore[misc]  # dspy (optional extra) is typed Any
        def __init__(self) -> None:
            super().__init__(
                model=f"korch/{model}", cache=False, num_retries=0, engine=_GatewayEngine()
            )

    lm: Any = _GatewayLM()
    return lm


def _request_messages(request: Any) -> list[dict[str, Any]]:
    """Flatten an lm15 ``Request`` (system prompt plus text parts) into chat-message dicts."""
    raw: list[dict[str, Any]] = []
    if request.system:
        raw.append({"role": "system", "content": _parts_text(request.system)})
    for message in request.messages:
        raw.append({"role": message.role, "content": _parts_text(message.parts)})
    return raw


def _parts_text(parts: Any) -> str:
    """Join the text of ``parts`` (a plain string passes through; non-text parts are skipped)."""
    if isinstance(parts, str):
        return parts
    return "".join(str(text) for text in (getattr(part, "text", None) for part in parts) if text)


def _build_gateway_lm_legacy(dspy: Any, gateway: IModelGateway, model: str) -> Any:
    """For dspy < 3.5: a ``dspy.LM`` whose ``__call__`` returns the reply as ``list[str]``."""

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
