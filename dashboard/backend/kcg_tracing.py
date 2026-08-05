"""Optional KCG (Kendra Control Gateway) tracing for the dashboard's demo swarms.

Mirrors tracing.py's shape exactly, but exports to KCG instead of LangSmith — the two are
independent, stackable gateway wrappers so a single demo run can emit to both platforms at once
(see each router's `_build_gateway()`). App-level only, no SDK changes: korchestrator has its own
OTel-based telemetry (korchestrator.telemetry); KCG is a per-app observability choice for these
demos, wired here.

KCG's ingest endpoint speaks standard OTLP/HTTP; this sends the JSON encoding (rather than the
default protobuf one used by the official OTel SDK exporters) so no opentelemetry-sdk/grpc
dependency is needed for a handful of spans — OTLP/HTTP JSON is a first-class encoding per the
OTLP spec, and KCG's parser (src/services/observability/otlp_parser.py) reads it directly. Spans
carry OpenInference semantic-convention attributes (openinference.span.kind=LLM, input.value,
output.value) so KCG's SpanRouter enriches them into Decision/Event graph nodes automatically.

Enabled only when a KCG API key is present in the environment; a network problem talking to KCG
is swallowed (logged, not raised) so tracing can never break a demo run.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from typing import Any

from korchestrator.models.state import Message

__all__ = ["KCGTracedGateway", "kcg_tracing_enabled"]

logger = logging.getLogger("dashboard.kcg_tracing")

_DEFAULT_BASE_URL = "http://localhost:8503"
_MAX_ATTR_CHARS = 8000


def kcg_tracing_enabled() -> bool:
    """Whether a KCG API key is configured."""
    return bool(os.environ.get("KCG_API_KEY"))


def _base_url() -> str:
    return os.environ.get("KCG_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _hex_id(nbytes: int) -> str:
    return secrets.token_hex(nbytes)


def _string_attr(key: str, value: str) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": value[:_MAX_ATTR_CHARS]}}


class KCGTracedGateway:
    """Wraps any IModelGateway to export each completion as an OTLP span to KCG.

    A no-op pass-through when kcg_tracing_enabled() is False, so callers can wrap
    unconditionally. Stack with TracedGateway (LangSmith) to emit to both platforms from one
    call: ``KCGTracedGateway(TracedGateway(inner, project=...), service_name=...)``.
    """

    def __init__(self, inner: Any, *, service_name: str) -> None:
        self._inner = inner
        self._service_name = service_name
        self._trace_id = _hex_id(16)

    async def complete(
        self, messages: list[Message], *, model: str, max_tokens: int | None = None
    ) -> Message:
        if not kcg_tracing_enabled():
            return await self._inner.complete(messages, model=model, max_tokens=max_tokens)

        start_ns = time.time_ns()
        try:
            reply = await self._inner.complete(messages, model=model, max_tokens=max_tokens)
        except Exception as exc:
            await self._export_span(messages, model, start_ns, time.time_ns(), output=None, error=str(exc))
            raise

        await self._export_span(
            messages, model, start_ns, time.time_ns(), output=reply.content, error=None
        )
        return reply

    async def available_models(self) -> list:
        return await self._inner.available_models()

    async def _export_span(
        self,
        messages: list[Message],
        model: str,
        start_ns: int,
        end_ns: int,
        *,
        output: str | None,
        error: str | None,
    ) -> None:
        try:
            import httpx
        except ImportError:
            logger.warning("kcg_tracing: httpx not installed, skipping export")
            return

        inputs = json.dumps([{"role": m.role.value, "content": m.content} for m in messages])
        attributes = [
            _string_attr("openinference.span.kind", "LLM"),
            _string_attr("llm.model_name", model),
            _string_attr("llm.provider", "openai"),
            _string_attr("input.value", inputs),
            _string_attr("input.mime_type", "application/json"),
        ]
        if error is not None:
            attributes.append(_string_attr("error.message", error))
            status = {"code": 2, "message": error[:_MAX_ATTR_CHARS]}
        else:
            attributes.append(_string_attr("output.value", output or ""))
            attributes.append(_string_attr("output.mime_type", "text/plain"))
            status = {"code": 1}

        span = {
            "traceId": self._trace_id,
            "spanId": _hex_id(8),
            "name": f"korchestrator.{self._service_name}.complete",
            "kind": 3,  # SPAN_KIND_CLIENT
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns),
            "attributes": attributes,
            "status": status,
        }
        resource_attributes = [_string_attr("service.name", self._service_name)]
        project_id = os.environ.get("KCG_PROJECT_ID")
        if project_id:
            resource_attributes.append(_string_attr("kcg.project_id", project_id))

        payload = {
            "resourceSpans": [
                {
                    "resource": {"attributes": resource_attributes},
                    "scopeSpans": [
                        {"scope": {"name": "korchestrator-dashboard"}, "spans": [span]}
                    ],
                }
            ]
        }
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("KCG_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(f"{_base_url()}/v1/traces", json=payload, headers=headers)
                if response.status_code >= 400:
                    logger.warning(
                        "kcg_tracing.export_failed status=%s body=%s",
                        response.status_code,
                        response.text[:300],
                    )
        except Exception as exc:  # tracing must never break a demo run
            logger.warning("kcg_tracing.export_error: %s", exc)
