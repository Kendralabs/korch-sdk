"""Client layer.

Allowed imports (beyond stdlib + pydantic): models, exceptions, config; httpx. Extra: [remote].

The remote HTTP client, re-exported as ``korchestrator.remote.KorchestratorClient`` — never
imported by the base ``korchestrator`` package (spec 04 §2 Tier 4; ``korchestrator/__init__.py``
does not import ``clients`` or ``remote``). Importing ``httpx`` at module top level here is
therefore safe for the base install: it mirrors ``runtime/temporal_runtime.py``'s
confinement-by-never-being-imported pattern, not a function-local lazy import (CLAUDE.md §3).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from types import TracebackType

import httpx
from typing_extensions import Self

from korchestrator.exceptions import ApiError, NetworkError
from korchestrator.exceptions import TimeoutError as KorchTimeoutError

__all__ = ["KorchestratorClient"]

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
_BACKOFF_BASE_SECONDS = 0.5


class KorchestratorClient:
    """Thin client for a hosted Korchestrator engine (spec 04 §7, Tier 4, the ``[remote]`` extra).

    Speaks the documented remote contract over HTTP: one ``Authorization: Bearer`` header for
    both a static API key and a Keycloak/KIAM JWT (spec 04 §7.2, ADR 0005), a 30s default
    per-request timeout (overridable per call), and up to 3 retries with full-jitter exponential
    backoff on 429/502/503/504 and connection failures — never on any other 4xx, since retrying a
    client error is a defect (spec 04 §7.5). This class currently provides the authenticated,
    retrying transport only; the run-lifecycle/control/streaming/discovery methods land in later
    Phase 9 tasks. Nothing in Tiers 1-3 (``Korch``/``Swarm``/the kernel) depends on this client,
    and the base install never imports it.

    Example:
        >>> from korchestrator.remote import KorchestratorClient
        >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
        >>> client.close()
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Build a client bound to ``base_url``, authenticating with ``api_key`` when given.

        Args:
            base_url: The engine's base URL, e.g. ``"https://engine.example.com"``.
            api_key: A static per-tenant key or a Keycloak/KIAM JWT — both ride the same
                ``Authorization: Bearer`` header (spec 04 §7.2). Omit for an unauthenticated
                engine (local development only).
            timeout: The default per-request timeout in seconds; overridable per call.
            max_retries: How many times a retryable failure is retried before raising.
        """
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )
        self._max_retries = max_retries

    async def __aenter__(self) -> Self:
        """Support ``async with KorchestratorClient(...) as client:``."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the underlying connection pool on exit."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying connection pool (async)."""
        await self._client.aclose()

    def close(self) -> None:
        """Close the underlying connection pool (sync convenience wrapper around :meth:`aclose`)."""
        asyncio.run(self.aclose())

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send one authenticated request, retrying transient failures (spec 04 §7.5).

        Args:
            method: The HTTP method, e.g. ``"GET"``/``"POST"``.
            path: The request path, relative to the client's ``base_url``.
            json: An optional JSON-serializable request body.
            params: Optional query parameters.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The terminal 2xx :class:`httpx.Response`.

        Raises:
            ApiError: The engine responded with a non-2xx status after retries were exhausted.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.
        """
        attempt = 0
        while True:
            try:
                response = await self._client.request(
                    method, path, json=json, params=params, timeout=timeout
                )
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise KorchTimeoutError(
                        f"{method} {path} timed out after {attempt + 1} attempt(s) against "
                        f"{self._client.base_url}. Raise `timeout=` or check engine availability.",
                        code="KORCH_TIMEOUT",
                    ) from exc
                await self._sleep_backoff(attempt)
                attempt += 1
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise NetworkError(
                        f"{method} {path} could not reach {self._client.base_url} after "
                        f"{attempt + 1} attempt(s): {exc}. Check the engine URL and network path.",
                        code="KORCH_NETWORK_UNAVAILABLE",
                    ) from exc
                await self._sleep_backoff(attempt)
                attempt += 1
                continue
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                await self._sleep_backoff(attempt)
                attempt += 1
                continue
            if response.status_code >= 400:
                raise _api_error(method, path, response)
            return response

    async def _sleep_backoff(self, attempt: int) -> None:
        """Sleep with full-jitter exponential backoff before retry ``attempt + 1`` (spec §7.5)."""
        delay = _BACKOFF_BASE_SECONDS * (2**attempt)
        await asyncio.sleep(random.uniform(0, delay))  # noqa: S311 — retry jitter, not crypto


def _api_error(method: str, path: str, response: httpx.Response) -> ApiError:
    """Build an :class:`ApiError` from a terminal non-2xx response, parsing its body defensively.

    The remote contract (spec 04 §7.5) does not pin an error-body schema, so this degrades
    gracefully: a JSON object with ``message``/``code``/``trace_id`` fields is preferred; anything
    else falls back to the raw response text as the message, with no ``code``/``trace_id``.
    """
    detail = response.text.strip()
    code: str | None = None
    trace_id: str | None = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, Mapping):
        raw_message = body.get("message")
        if raw_message is not None:
            detail = str(raw_message)
        raw_code = body.get("code")
        code = str(raw_code) if raw_code is not None else None
        raw_trace_id = body.get("trace_id")
        trace_id = str(raw_trace_id) if raw_trace_id is not None else None
    message = f"{method} {path} failed with HTTP {response.status_code}" + (
        f": {detail}" if detail else "."
    )
    return ApiError(message, status=response.status_code, code=code, trace_id=trace_id)
