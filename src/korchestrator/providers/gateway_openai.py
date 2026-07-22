"""Adapter layer. Imports: korchestrator.models/exceptions, stdlib, httpx (lazy). Extra: [remote].

The default networked :class:`~korchestrator.interfaces.IModelGateway` — ``OpenAIGateway``: a thin
client for any OpenAI-compatible chat-completions endpoint (spec 03 §5). All configuration
(endpoint, credentials, timeout) is **injected** — the gateway reads no environment (spec 07 §5) —
and every vendor (`httpx`) exception is wrapped as a :class:`~korchestrator.exceptions.KorchError`
subclass so no transport detail crosses the boundary (spec 08 §2.2). ``httpx`` is imported lazily
inside the calling method and belongs to the ``[remote]`` extra, so the base install stays
``pydantic``-only.

This module lives outside workflow scope; network I/O and its timing are an activity boundary, never
kernel code (``.claude/rules/determinism.md``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone

from korchestrator.exceptions import (
    AuthError,
    ProviderError,
    RateLimitError,
    TimeoutError,  # noqa: A004 — deliberately the KorchError timeout, not the builtin (spec 08 §2.1)
    ValidationError,
)
from korchestrator.models.routing import ModelCard
from korchestrator.models.state import Message, MessageRole

__all__ = ["OpenAIGateway"]

# The agent layer re-stamps ``valid_time`` from the injected clock when it folds the completion into
# a StateUpdate; this placeholder keeps the returned Message free of a wall-clock read.
_PLACEHOLDER_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

# The OpenAI ``/models`` endpoint reports no capability metadata, so ``available_models`` fills
# these documented, conservative placeholders. A routing catalogue or enterprise gateway overrides.
_PLACEHOLDER_CONTEXT_WINDOW = 4096
_PLACEHOLDER_QUALITY = 0.5


class OpenAIGateway:
    """Networked :class:`~korchestrator.interfaces.IModelGateway` for OpenAI-compatible endpoints.

    Calls ``POST {base_url}/chat/completions`` and returns the assistant reply as a
    :class:`~korchestrator.models.state.Message`. Every ``httpx`` failure is wrapped: a timeout
    becomes :class:`~korchestrator.exceptions.TimeoutError`, ``401``/``403`` becomes
    :class:`~korchestrator.exceptions.AuthError`, ``429`` becomes
    :class:`~korchestrator.exceptions.RateLimitError`, and anything else becomes
    :class:`~korchestrator.exceptions.ProviderError` — always with ``raise ... from exc``.

    Configuration is injected; the gateway reads no environment and logs neither prompts nor
    credentials (spec 07 §5). It is safe to call concurrently — each call owns its own HTTP client.

    Args:
        api_key: Bearer credential for the endpoint.
        base_url: The API root, e.g. ``https://api.openai.com/v1`` — required and injected, never
            hardcoded, so any OpenAI-compatible provider can be targeted.
        timeout_seconds: Per-request deadline. Defaults to ``30.0``.
        organization: Optional organization id sent as the ``OpenAI-Organization`` header.

    Example:
        >>> from korchestrator.providers import OpenAIGateway
        >>> gateway = OpenAIGateway(api_key="sk-...", base_url="https://api.openai.com/v1")
        >>> gateway.base_url
        'https://api.openai.com/v1'
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        organization: str | None = None,
    ) -> None:
        """Store the injected endpoint and credentials, validating that both are present."""
        if not api_key:
            raise ValidationError(
                "api_key must be a non-empty credential for the model endpoint. Provide the key "
                "for your OpenAI-compatible provider, or use MockLM for offline runs."
            )
        if not base_url:
            raise ValidationError(
                "base_url must be a non-empty endpoint root, e.g. 'https://api.openai.com/v1'. "
                "It is injected so any OpenAI-compatible provider can be targeted."
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._organization = organization

    @property
    def base_url(self) -> str:
        """The configured endpoint root (without a trailing slash)."""
        return self._base_url

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int | None = None,
    ) -> Message:
        """Send ``messages`` to ``model`` and return the assistant completion as a :class:`Message`.

        Args:
            messages: The conversation, mapped to OpenAI chat roles in order.
            model: The model id to call, e.g. ``"gpt-4o"``.
            max_tokens: Optional cap on generated tokens; omitted from the request when ``None``.

        Returns:
            The assistant reply as an immutable :class:`Message` (its ``valid_time`` is a
            placeholder the agent layer re-stamps from the injected clock).

        Raises:
            TimeoutError: The endpoint did not respond within ``timeout_seconds``.
            AuthError: The endpoint rejected the credentials (HTTP 401/403).
            RateLimitError: The endpoint rate-limited the request (HTTP 429).
            ProviderError: Any other transport failure or an unexpected response shape.
        """
        import httpx

        payload: dict[str, object] = {
            "model": model,
            "messages": [self._to_chat(message) for message in messages],
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout_seconds
            ) as client:
                response = await client.post(
                    "/chat/completions", json=payload, headers=self._headers()
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"OpenAI gateway did not respond within {self._timeout_seconds:g}s for model "
                f"{model!r}. Increase timeout_seconds or check endpoint availability.",
                model=model,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise self._status_error(exc.response.status_code, model) from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"OpenAI gateway returned a non-JSON response for model {model!r}.", model=model
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"OpenAI gateway request failed for model {model!r}: {exc}.", model=model
            ) from exc

        return self._message_from(data, model)

    async def available_models(self) -> list[ModelCard]:
        """List the endpoint's models via ``GET /models``.

        The ``/models`` endpoint reports ids only, so each card carries the real name and provider
        with documented placeholder capability metadata (see module constants); a routing catalogue
        or enterprise gateway supplies richer figures.

        Returns:
            One :class:`~korchestrator.models.routing.ModelCard` per advertised model.

        Raises:
            AuthError, RateLimitError, ProviderError, TimeoutError: As for :meth:`complete`.
        """
        import httpx

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout_seconds
            ) as client:
                response = await client.get("/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"OpenAI gateway did not respond within {self._timeout_seconds:g}s while listing "
                "models. Increase timeout_seconds or check endpoint availability.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise self._status_error(exc.response.status_code, model=None) from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "OpenAI gateway returned a non-JSON response while listing models."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI gateway model listing failed: {exc}.") from exc

        return self._cards_from(data)

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._organization is not None:
            headers["OpenAI-Organization"] = self._organization
        return headers

    @staticmethod
    def _to_chat(message: Message) -> dict[str, str]:
        return {"role": message.role.value, "content": message.content}

    @staticmethod
    def _status_error(status: int, model: str | None) -> AuthError | RateLimitError | ProviderError:
        target = f" for model {model!r}" if model else ""
        context = {"model": model} if model else {}
        if status in (401, 403):
            return AuthError(
                f"OpenAI gateway rejected the credentials (HTTP {status}){target}. Check the API "
                "key and its permissions.",
                **context,
            )
        if status == 429:
            return RateLimitError(
                f"OpenAI gateway rate-limited the request (HTTP 429){target}. Retry after backoff "
                "or lower the request rate.",
                **context,
            )
        return ProviderError(f"OpenAI gateway returned HTTP {status}{target}.", **context)

    @staticmethod
    def _message_from(data: object, model: str) -> Message:
        if not isinstance(data, Mapping):
            raise ProviderError(
                f"OpenAI gateway returned an unexpected response shape for model {model!r}.",
                model=model,
            )
        try:
            content = data["choices"][0]["message"]["content"]
            response_id = str(data.get("id", "openai-gateway"))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"OpenAI gateway returned an unexpected response shape for model {model!r}.",
                model=model,
            ) from exc
        return Message(
            id=response_id,
            role=MessageRole.ASSISTANT,
            content=str(content),
            sender="assistant",
            superstep=0,
            valid_time=_PLACEHOLDER_TIME,
        )

    @staticmethod
    def _cards_from(data: object) -> list[ModelCard]:
        entries = data.get("data", []) if isinstance(data, Mapping) else None
        if not isinstance(entries, list):
            raise ProviderError("OpenAI gateway returned an unexpected shape while listing models.")
        cards: list[ModelCard] = []
        for entry in entries:
            if not isinstance(entry, Mapping) or "id" not in entry:
                continue
            name = str(entry["id"])
            description = f"OpenAI-compatible model {name}; capability metadata is a placeholder."
            cards.append(
                ModelCard(
                    name=name,
                    provider=str(entry.get("owned_by", "openai")),
                    description=description,
                    context_window=_PLACEHOLDER_CONTEXT_WINDOW,
                    cost_per_1k_input_usd=0.0,
                    cost_per_1k_output_usd=0.0,
                    latency_p50_ms=0,
                    quality_score=_PLACEHOLDER_QUALITY,
                )
            )
        return cards
