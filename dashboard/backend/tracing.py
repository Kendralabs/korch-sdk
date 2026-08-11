"""Optional LangSmith tracing for the dashboard's demo swarms — app-level only, no SDK changes.

korchestrator itself has its own OTel-based telemetry (korchestrator.telemetry), which is the
right place for anything the SDK should own. LangSmith is a per-app observability choice for
these demos specifically, so it's wired here, not in the SDK. Enabled only when a LangSmith API
key is present in the environment; a network problem talking to LangSmith is swallowed (logged,
not raised) so tracing can never break a demo run.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from korchestrator.models.state import Message

__all__ = ["TracedGateway", "tracing_enabled"]

logger = logging.getLogger("dashboard.tracing")

_client: Any = None


def tracing_enabled() -> bool:
    """Whether a LangSmith API key is configured (new LANGSMITH_* or legacy LANGCHAIN_* name)."""
    return bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY"))


def _project_name() -> str:
    return (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or "korchestrator-dashboard"
    )


def _get_client() -> Any:
    global _client
    if _client is None:
        from langsmith import Client

        _client = Client()
    return _client


class TracedGateway:
    """Wraps any IModelGateway to log each completion as a LangSmith LLM run.

    A no-op pass-through when tracing_enabled() is False, so callers can wrap unconditionally.
    """

    def __init__(self, inner: Any, *, project: str | None = None) -> None:
        self._inner = inner
        self._project = project or _project_name()

    async def complete(
        self, messages: list[Message], *, model: str, max_tokens: int | None = None
    ) -> Message:
        if not tracing_enabled():
            return await self._inner.complete(messages, model=model, max_tokens=max_tokens)

        client = _get_client()
        run_id = str(uuid.uuid4())
        inputs = {
            "model": model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
        }
        try:
            client.create_run(
                id=run_id,
                name="korchestrator.gateway.complete",
                run_type="llm",
                inputs=inputs,
                project_name=self._project,
                start_time=datetime.now(timezone.utc),
            )
        except Exception as exc:  # tracing must never break a demo run
            logger.warning("langsmith.create_run failed: %s", exc)

        try:
            reply = await self._inner.complete(messages, model=model, max_tokens=max_tokens)
        except Exception as exc:
            try:
                client.update_run(run_id, error=str(exc), end_time=datetime.now(timezone.utc))
            except Exception as trace_exc:
                logger.warning("langsmith.update_run (error path) failed: %s", trace_exc)
            raise

        try:
            client.update_run(
                run_id, outputs={"content": reply.content}, end_time=datetime.now(timezone.utc)
            )
        except Exception as exc:
            logger.warning("langsmith.update_run failed: %s", exc)
        return reply

    async def available_models(self) -> list:
        return await self._inner.available_models()
