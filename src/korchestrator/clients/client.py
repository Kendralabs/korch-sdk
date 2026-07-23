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
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import TypeVar

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from typing_extensions import Self

from korchestrator.exceptions import ApiError, NetworkError
from korchestrator.exceptions import TimeoutError as KorchTimeoutError
from korchestrator.models.agent import AgentConfig
from korchestrator.models.remote import (
    ApiKey,
    ApiKeySummary,
    CallerIdentity,
    Quota,
    RemoteRunResult,
    RunSummary,
)
from korchestrator.models.state import RunStatus
from korchestrator.types import JSONValue

__all__ = ["KorchestratorClient"]

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
_BACKOFF_BASE_SECONDS = 0.5
_TERMINAL_STATUSES = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.TIMED_OUT}
)
# The numeric->string status normalization spec 04 §7.4 documents explicitly (1/2/3/4/6); 0 and 5
# are the two RunStatus values the table leaves implicit — "started" precedes "running" in the
# lifecycle diagram, and "governance_paused" is the only status the table omits outright.
_STATUS_BY_CODE: dict[int, RunStatus] = {
    0: RunStatus.STARTED,
    1: RunStatus.RUNNING,
    2: RunStatus.COMPLETED,
    3: RunStatus.FAILED,
    4: RunStatus.CANCELLED,
    5: RunStatus.GOVERNANCE_PAUSED,
    6: RunStatus.TIMED_OUT,
}
_ModelT = TypeVar("_ModelT", bound=BaseModel)


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

    def __repr__(self) -> str:
        """Show ``base_url`` only — never the credential (spec 04 §7.2: never logged/printed)."""
        return f"KorchestratorClient(base_url={str(self._client.base_url)!r})"

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

    # --- run lifecycle (spec 04 §7.3/§7.4, P9.3) -------------------------------------------------

    def run(
        self,
        objective: str,
        *,
        max_supersteps: int = 10,
        mock_mode: bool = False,
        tenant_id: str | None = None,
        timeout: float | None = None,
    ) -> RemoteRunResult:
        """Start a run; the engine plans the graph (``POST /v1/run/auto``).

        Returns as soon as the engine has accepted the run — typically ``status="started"`` or
        ``"running"``, not necessarily terminal. Use :meth:`wait` or :meth:`run_and_wait` to block
        until a terminal state.

        Args:
            objective: The goal, at least 10 characters.
            max_supersteps: Hard halt bound for the run.
            mock_mode: Run with a deterministic mock model (spec 04 §7.1).
            tenant_id: Overrides the tenant derived from the API key, when the caller is
                authorized to act cross-tenant.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The run's initial :class:`~korchestrator.models.remote.RemoteRunResult`.

        Raises:
            ApiError: The engine rejected or failed the request.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.run("Summarize the quarterly incident reports")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(
            self._run_async(
                objective,
                max_supersteps=max_supersteps,
                mock_mode=mock_mode,
                tenant_id=tenant_id,
                timeout=timeout,
            )
        )

    async def _run_async(
        self,
        objective: str,
        *,
        max_supersteps: int,
        mock_mode: bool,
        tenant_id: str | None,
        timeout: float | None,
    ) -> RemoteRunResult:
        body: dict[str, object] = {
            "objective": objective,
            "max_supersteps": max_supersteps,
            "mock_mode": mock_mode,
        }
        if tenant_id is not None:
            body["tenant_id"] = tenant_id
        response = await self._request("POST", "/v1/run/auto", json=body, timeout=timeout)
        return _validate_model(RemoteRunResult, _parse_json_body(response), response.status_code)

    def run_swarm(
        self,
        agents: Sequence[AgentConfig],
        edges: Sequence[tuple[str, str]] = (),
        *,
        objective: str,
        max_supersteps: int = 10,
        tenant_id: str | None = None,
        timeout: float | None = None,
    ) -> RemoteRunResult:
        """Start a run with an explicit graph (``POST /v1/run/swarm``).

        Args:
            agents: The declared agents, as the same :class:`AgentConfig` shape ``Swarm`` uses.
            edges: ``(source_id, target_id)`` pairs; empty means every agent is independent.
            objective: The goal, at least 10 characters.
            max_supersteps: Hard halt bound for the run.
            tenant_id: Overrides the tenant derived from the API key, when authorized.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The run's initial :class:`~korchestrator.models.remote.RemoteRunResult`.

        Raises:
            ApiError: The engine rejected or failed the request.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.models import AgentConfig, AgentPersona
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> agent = AgentConfig(id="lead", persona=AgentPersona(role="lead"))
            >>> client.run_swarm([agent], objective="Review this PR")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(
            self._run_swarm_async(
                agents,
                edges,
                objective=objective,
                max_supersteps=max_supersteps,
                tenant_id=tenant_id,
                timeout=timeout,
            )
        )

    async def _run_swarm_async(
        self,
        agents: Sequence[AgentConfig],
        edges: Sequence[tuple[str, str]],
        *,
        objective: str,
        max_supersteps: int,
        tenant_id: str | None,
        timeout: float | None,
    ) -> RemoteRunResult:
        body: dict[str, object] = {
            "objective": objective,
            "agents": [agent.model_dump(mode="json") for agent in agents],
            "edges": [list(edge) for edge in edges],
            "max_supersteps": max_supersteps,
        }
        if tenant_id is not None:
            body["tenant_id"] = tenant_id
        response = await self._request("POST", "/v1/run/swarm", json=body, timeout=timeout)
        return _validate_model(RemoteRunResult, _parse_json_body(response), response.status_code)

    def get_run(self, run_id: str, *, timeout: float | None = None) -> RemoteRunResult:
        """Fetch a run's full live state (``GET /v1/run/{id}``).

        Args:
            run_id: The run to fetch.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The run's current :class:`~korchestrator.models.remote.RemoteRunResult`.

        Raises:
            ApiError: The engine rejected the request or the run does not exist.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.get_run("r1")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._get_run_async(run_id, timeout=timeout))

    async def _get_run_async(self, run_id: str, *, timeout: float | None) -> RemoteRunResult:
        response = await self._request("GET", f"/v1/run/{run_id}", timeout=timeout)
        return _validate_model(RemoteRunResult, _parse_json_body(response), response.status_code)

    def wait(
        self,
        run_id: str,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        timeout: float | None = None,
    ) -> RemoteRunResult:
        """Block until ``run_id`` reaches a terminal state, polling :meth:`get_run`.

        A ``governance_paused`` run is not terminal — it stays pending until an operator calls
        :meth:`resume`/``cancel``/``edit_resume`` (P9.4), so this keeps polling through it rather
        than returning early.

        Args:
            run_id: The run to wait for.
            poll_interval: Seconds between polls.
            timeout: Per-request timeout passed to each poll; does not bound the total wait.

        Returns:
            The terminal :class:`~korchestrator.models.remote.RemoteRunResult`.

        Raises:
            ApiError: The engine rejected the request or the run does not exist.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: A poll request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.wait("r1")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._wait_async(run_id, poll_interval=poll_interval, timeout=timeout))

    async def _wait_async(
        self, run_id: str, *, poll_interval: float, timeout: float | None
    ) -> RemoteRunResult:
        while True:
            result = await self._get_run_async(run_id, timeout=timeout)
            if result.status in _TERMINAL_STATUSES:
                return result
            await asyncio.sleep(poll_interval)

    def run_and_wait(
        self,
        objective: str,
        *,
        max_supersteps: int = 10,
        mock_mode: bool = False,
        tenant_id: str | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        timeout: float | None = None,
    ) -> RemoteRunResult:
        """Start a run and block until it reaches a terminal state (``run`` + ``wait``).

        Args:
            objective: The goal, at least 10 characters.
            max_supersteps: Hard halt bound for the run.
            mock_mode: Run with a deterministic mock model.
            tenant_id: Overrides the tenant derived from the API key, when authorized.
            poll_interval: Seconds between polls while waiting.
            timeout: Per-request timeout passed to the start call and every poll.

        Returns:
            The terminal :class:`~korchestrator.models.remote.RemoteRunResult`.

        Raises:
            ApiError: The engine rejected or failed the request.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: A request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.run_and_wait("Summarize Q3 incident reports")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(
            self._run_and_wait_async(
                objective,
                max_supersteps=max_supersteps,
                mock_mode=mock_mode,
                tenant_id=tenant_id,
                poll_interval=poll_interval,
                timeout=timeout,
            )
        )

    async def _run_and_wait_async(
        self,
        objective: str,
        *,
        max_supersteps: int,
        mock_mode: bool,
        tenant_id: str | None,
        poll_interval: float,
        timeout: float | None,
    ) -> RemoteRunResult:
        started = await self._run_async(
            objective,
            max_supersteps=max_supersteps,
            mock_mode=mock_mode,
            tenant_id=tenant_id,
            timeout=timeout,
        )
        return await self._wait_async(started.run_id, poll_interval=poll_interval, timeout=timeout)

    def list_runs(
        self, *, tenant_id: str | None = None, timeout: float | None = None
    ) -> tuple[RunSummary, ...]:
        """List runs visible to the caller (``GET /v1/runs``).

        Args:
            tenant_id: Overrides the tenant derived from the API key, when authorized.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The visible runs as :class:`~korchestrator.models.remote.RunSummary`.

        Raises:
            ApiError: The engine rejected the request.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.list_runs()  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._list_runs_async(tenant_id=tenant_id, timeout=timeout))

    async def _list_runs_async(
        self, *, tenant_id: str | None, timeout: float | None
    ) -> tuple[RunSummary, ...]:
        params = {"tenant_id": tenant_id} if tenant_id is not None else None
        response = await self._request("GET", "/v1/runs", params=params, timeout=timeout)
        payload = _parse_json_body(response)
        items = _extract_list(payload, "runs", response.status_code)
        return tuple(_validate_model(RunSummary, item, response.status_code) for item in items)

    def get_run_summary(self, run_id: str, *, timeout: float | None = None) -> RunSummary:
        """Fetch a run's summary (``GET /v1/runs/{id}/summary``).

        Args:
            run_id: The run to summarize.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The run's :class:`~korchestrator.models.remote.RunSummary`.

        Raises:
            ApiError: The engine rejected the request or the run does not exist.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.get_run_summary("r1")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._get_run_summary_async(run_id, timeout=timeout))

    async def _get_run_summary_async(self, run_id: str, *, timeout: float | None) -> RunSummary:
        response = await self._request("GET", f"/v1/runs/{run_id}/summary", timeout=timeout)
        return _validate_model(RunSummary, _parse_json_body(response), response.status_code)

    # --- control + identity (spec 04 §7.3, P9.4) ---------------------------------------------

    def resume(self, run_id: str, *, timeout: float | None = None) -> RemoteRunResult:
        """Resume a ``governance_paused`` run (``POST /v1/run/{id}/resume``).

        Args:
            run_id: The paused run to resume.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The run's :class:`~korchestrator.models.remote.RemoteRunResult` after resuming.

        Raises:
            ApiError: The engine rejected the request or the run is not paused.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.resume("r1")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._resume_async(run_id, timeout=timeout))

    async def _resume_async(self, run_id: str, *, timeout: float | None) -> RemoteRunResult:
        response = await self._request("POST", f"/v1/run/{run_id}/resume", timeout=timeout)
        return _validate_model(RemoteRunResult, _parse_json_body(response), response.status_code)

    def cancel(self, run_id: str, *, timeout: float | None = None) -> RemoteRunResult:
        """Cancel a run (``POST /v1/run/{id}/cancel``).

        Args:
            run_id: The run to cancel.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The run's :class:`~korchestrator.models.remote.RemoteRunResult` after cancelling.

        Raises:
            ApiError: The engine rejected the request or the run does not exist.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.cancel("r1")  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._cancel_async(run_id, timeout=timeout))

    async def _cancel_async(self, run_id: str, *, timeout: float | None) -> RemoteRunResult:
        response = await self._request("POST", f"/v1/run/{run_id}/cancel", timeout=timeout)
        return _validate_model(RemoteRunResult, _parse_json_body(response), response.status_code)

    def edit_resume(
        self,
        run_id: str,
        *,
        updates: Mapping[str, JSONValue] | None = None,
        trust_delta: float = 0.0,
        timeout: float | None = None,
    ) -> RemoteRunResult:
        """Modify a ``governance_paused`` run's state and resume it (``POST .../edit-resume``).

        Mirrors the local kernel's own ``edit_resume`` signal (``services.Korch.edit_resume``):
        ``updates`` are merged last-value into the run's context channel, and ``trust_delta`` is
        folded into ``trust_score``.

        Args:
            run_id: The paused run to edit and resume.
            updates: Context-channel values to merge (last-value) into the paused run's state.
            trust_delta: Folded into ``trust_score`` by the engine's own clamp.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The run's :class:`~korchestrator.models.remote.RemoteRunResult` after resuming.

        Raises:
            ApiError: The engine rejected the request or the run is not paused.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.edit_resume("r1", trust_delta=0.1)  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(
            self._edit_resume_async(
                run_id, updates=updates, trust_delta=trust_delta, timeout=timeout
            )
        )

    async def _edit_resume_async(
        self,
        run_id: str,
        *,
        updates: Mapping[str, JSONValue] | None,
        trust_delta: float,
        timeout: float | None,
    ) -> RemoteRunResult:
        body = {"updates": dict(updates or {}), "trust_delta": trust_delta}
        response = await self._request(
            "POST", f"/v1/run/{run_id}/edit-resume", json=body, timeout=timeout
        )
        return _validate_model(RemoteRunResult, _parse_json_body(response), response.status_code)

    def me(self, *, timeout: float | None = None) -> CallerIdentity:
        """Fetch the authenticated caller's identity (``GET /v1/me``).

        Args:
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The caller's :class:`~korchestrator.models.remote.CallerIdentity`.

        Raises:
            ApiError: The engine rejected the request.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.me()  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._me_async(timeout=timeout))

    async def _me_async(self, *, timeout: float | None) -> CallerIdentity:
        response = await self._request("GET", "/v1/me", timeout=timeout)
        return _validate_model(CallerIdentity, _parse_json_body(response), response.status_code)

    def my_quota(self, *, timeout: float | None = None) -> Quota:
        """Fetch the authenticated caller's usage quota (``GET /v1/me/quota``).

        Args:
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The caller's :class:`~korchestrator.models.remote.Quota`.

        Raises:
            ApiError: The engine rejected the request.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.my_quota()  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._my_quota_async(timeout=timeout))

    async def _my_quota_async(self, *, timeout: float | None) -> Quota:
        response = await self._request("GET", "/v1/me/quota", timeout=timeout)
        return _validate_model(Quota, _parse_json_body(response), response.status_code)

    def my_runs(self, *, timeout: float | None = None) -> tuple[RunSummary, ...]:
        """List the authenticated caller's runs (``GET /v1/me/runs``).

        Args:
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The caller's runs as :class:`~korchestrator.models.remote.RunSummary`.

        Raises:
            ApiError: The engine rejected the request.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.my_runs()  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._my_runs_async(timeout=timeout))

    async def _my_runs_async(self, *, timeout: float | None) -> tuple[RunSummary, ...]:
        response = await self._request("GET", "/v1/me/runs", timeout=timeout)
        payload = _parse_json_body(response)
        items = _extract_list(payload, "runs", response.status_code)
        return tuple(_validate_model(RunSummary, item, response.status_code) for item in items)

    def create_key(self, *, scopes: Sequence[str] = (), timeout: float | None = None) -> ApiKey:
        """Create a new API key (``POST /v1/keys``, the ``korchestrator:admin`` scope).

        The returned secret is shown once — the engine never returns it again.

        Args:
            scopes: The scopes to grant the new key.
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The newly created :class:`~korchestrator.models.remote.ApiKey`.

        Raises:
            ApiError: The engine rejected the request (e.g. insufficient scope).
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.create_key(scopes=["korchestrator:read"])  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._create_key_async(scopes=scopes, timeout=timeout))

    async def _create_key_async(self, *, scopes: Sequence[str], timeout: float | None) -> ApiKey:
        body = {"scopes": list(scopes)}
        response = await self._request("POST", "/v1/keys", json=body, timeout=timeout)
        return _validate_model(ApiKey, _parse_json_body(response), response.status_code)

    def list_keys(self, *, timeout: float | None = None) -> tuple[ApiKeySummary, ...]:
        """List existing API keys (``GET /v1/keys``, the ``korchestrator:admin`` scope).

        Args:
            timeout: Overrides the client's default timeout for this call only.

        Returns:
            The tenant's keys as :class:`~korchestrator.models.remote.ApiKeySummary` — never the
            secret, which the engine only ever returns once, at creation.

        Raises:
            ApiError: The engine rejected the request (e.g. insufficient scope).
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.list_keys()  # doctest: +SKIP
            >>> client.close()
        """
        return asyncio.run(self._list_keys_async(timeout=timeout))

    async def _list_keys_async(self, *, timeout: float | None) -> tuple[ApiKeySummary, ...]:
        response = await self._request("GET", "/v1/keys", timeout=timeout)
        payload = _parse_json_body(response)
        items = _extract_list(payload, "keys", response.status_code)
        return tuple(_validate_model(ApiKeySummary, item, response.status_code) for item in items)

    def revoke_key(self, key_id: str, *, timeout: float | None = None) -> None:
        """Revoke an API key (``DELETE /v1/keys/{id}``, the ``korchestrator:admin`` scope).

        Args:
            key_id: The key to revoke.
            timeout: Overrides the client's default timeout for this call only.

        Raises:
            ApiError: The engine rejected the request or the key does not exist.
            NetworkError: The connection failed after retries were exhausted.
            TimeoutError: The request timed out after retries were exhausted.

        Example:
            >>> from korchestrator.remote import KorchestratorClient
            >>> client = KorchestratorClient("https://engine.example.com", api_key="sk-example")
            >>> client.revoke_key("key-1")  # doctest: +SKIP
            >>> client.close()
        """
        asyncio.run(self._revoke_key_async(key_id, timeout=timeout))

    async def _revoke_key_async(self, key_id: str, *, timeout: float | None) -> None:
        await self._request("DELETE", f"/v1/keys/{key_id}", timeout=timeout)


def _parse_json_body(response: httpx.Response) -> object:
    """Parse ``response``'s JSON body, wrapping a malformed body as an :class:`ApiError`."""
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError(
            f"The engine returned a non-JSON response for {response.request.url}.",
            status=response.status_code,
        ) from exc


def _normalize_status_field(payload: Mapping[str, object]) -> dict[str, object]:
    """Apply spec 04 §7.4's numeric->string run-status normalization, if ``status`` is numeric."""
    normalized = dict(payload)
    status = normalized.get("status")
    if isinstance(status, int) and not isinstance(status, bool):
        try:
            normalized["status"] = _STATUS_BY_CODE[status].value
        except KeyError as exc:
            raise ApiError(
                f"The engine returned an unrecognised numeric run status {status!r}.", status=502
            ) from exc
    return normalized


def _validate_model(model_cls: type[_ModelT], payload: object, status_code: int) -> _ModelT:
    """Validate ``payload`` into ``model_cls``, normalizing a numeric ``status`` field first.

    Wraps a shape mismatch or a ``pydantic`` validation failure as an :class:`ApiError` — the one
    documented error type for a failed :class:`KorchestratorClient` call (spec 04 §7.5).
    """
    if not isinstance(payload, Mapping):
        raise ApiError(
            f"The engine returned an unexpected {model_cls.__name__} response shape: {payload!r}.",
            status=status_code,
        )
    try:
        return model_cls.model_validate(_normalize_status_field(payload))
    except PydanticValidationError as exc:
        raise ApiError(
            f"The engine's response did not match the expected {model_cls.__name__} shape: {exc}",
            status=status_code,
        ) from exc


def _extract_list(payload: object, key: str, status_code: int) -> list[object]:
    """Extract a list from either a bare JSON array or a ``{key: [...]}`` wrapper object."""
    if isinstance(payload, list):
        items: object = payload
    elif isinstance(payload, Mapping) and key in payload:
        items = payload[key]
    else:
        items = None
    if not isinstance(items, list):
        raise ApiError(
            f"The engine returned an unexpected list response shape: {payload!r}.",
            status=status_code,
        )
    return items


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
