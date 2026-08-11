"""Optional KCG (Kendra Control Gateway) tracing for the dashboard's demo swarms.

Mirrors tracing.py's shape exactly, but exports to KCG instead of LangSmith — the two are
independent, stackable gateway wrappers so a single demo run can emit to both platforms at once
(see each router's `_build_gateway()`). App-level only, no SDK changes: korchestrator has its own
OTel-based telemetry (korchestrator.telemetry); KCG is a per-app observability choice for these
demos, wired here.

Each completed LLM call is dual-written to two independent KCG surfaces, because KCG's own
SpanRouter (src/services/span_ingestion/open_inference.py) maps OpenInference LLM-kind spans to
"ModelCall" graph nodes, not "Decision" nodes — only the latter feed KCG's Analytics dashboard
(src/api/routes/analytics.py's analytics_summary literally filters `n.label == "Decision"`).
Sending only OTLP spans makes the Traces page work but leaves Analytics ("Total Decisions",
"Active Agents", "Run Status") empty, which is confusing without knowing that internal split.
So:

1. An OTLP/HTTP JSON span (`POST /v1/traces`) with OpenInference attributes — feeds the Traces
   page and KCG's cost/latency-oriented ModelCall enrichment. JSON, not the OTel SDK's default
   protobuf encoding, so no opentelemetry-sdk/grpc dependency is needed for a handful of spans;
   OTLP/HTTP JSON is a first-class encoding per the OTLP spec.
2. A graph "Decision" node (`POST /ingest`) with agent_id/run_id/confidence — feeds the Analytics
   dashboard directly, the same graph-native shape KCG's own demo (src/demos/swarm_kcg_demo.py)
   uses. confidence_score is a fixed estimate (0.85): the SDK has no real confidence signal to
   report, so this is a placeholder, not a measured value — same honesty bar as the fincrime
   demo's approximate token/cost estimates elsewhere in this dashboard.

Enabled only when a KCG API key is present in the environment; a network problem talking to KCG
is swallowed (logged, not raised) so tracing can never break a demo run.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from korchestrator.models.state import Message

__all__ = ["KCGTracedGateway", "kcg_tracing_enabled"]

logger = logging.getLogger("dashboard.kcg_tracing")

_DEFAULT_BASE_URL = "http://localhost:8503"
_MAX_ATTR_CHARS = 8000
_DECISION_CONFIDENCE = 0.85

# DSPy's ChatAdapter renders each worker's prompt with this exact marker (established convention
# across every gateway in this dashboard — see researcher_router.py's OfflineGateway for the same
# format on the output side). Used here only as a best-effort agent-id label for KCG's Analytics
# per-agent breakdown; falls back to the service name when the marker isn't present.
_ROLE_MARKER = re.compile(r"\[\[ ## role ## \]\]\n(.+?)\n")


def kcg_tracing_enabled() -> bool:
    """Whether a KCG API key is configured."""
    return bool(os.environ.get("KCG_API_KEY"))


def _base_url() -> str:
    return os.environ.get("KCG_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _hex_id(nbytes: int) -> str:
    return secrets.token_hex(nbytes)


def _string_attr(key: str, value: str) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": value[:_MAX_ATTR_CHARS]}}


def _extract_agent_id(messages: list[Message], fallback: str) -> str:
    # The system message contains the DSPy signature *template* itself, which includes this
    # exact marker followed by the literal placeholder text "{role}" (describing the field, not
    # its value) — only the user message carries the filled-in role. Skip any match whose
    # captured text is itself a bare `{...}` placeholder so the template line is never returned.
    for m in messages:
        for match in _ROLE_MARKER.finditer(m.content):
            value = match.group(1).strip()
            if value and not (value.startswith("{") and value.endswith("}")):
                return value[:120]
    return fallback


class KCGTracedGateway:
    """Wraps any IModelGateway to export each completion to KCG as both an OTLP span (Traces
    page) and a Decision graph node (Analytics page) — see module docstring for why both.

    A no-op pass-through when kcg_tracing_enabled() is False, so callers can wrap
    unconditionally. Stack with TracedGateway (LangSmith) to emit to both platforms from one
    call: ``KCGTracedGateway(TracedGateway(inner, project=...), service_name=...)``.
    """

    def __init__(self, inner: Any, *, service_name: str, run_id: str | None = None) -> None:
        self._inner = inner
        self._service_name = service_name
        self._run_id = run_id
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

        end_ns = time.time_ns()
        await self._export_span(messages, model, start_ns, end_ns, output=reply.content, error=None)
        await self._export_decision(messages, model, reply.content)
        return reply

    async def available_models(self) -> list:
        return await self._inner.available_models()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("KCG_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

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
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{_base_url()}/v1/traces", json=payload, headers=self._headers()
                )
                if response.status_code >= 400:
                    logger.warning(
                        "kcg_tracing.export_span_failed status=%s body=%s",
                        response.status_code,
                        response.text[:300],
                    )
        except Exception as exc:  # tracing must never break a demo run
            logger.warning("kcg_tracing.export_span_error: %s", exc)

    async def _export_decision(self, messages: list[Message], model: str, content: str) -> None:
        try:
            import httpx
        except ImportError:
            return

        agent_id = _extract_agent_id(messages, fallback=self._service_name)
        properties = {
            "agent_id": agent_id,
            "run_id": self._run_id or "",
            "service": self._service_name,
            "model": model,
            "trace_id": self._trace_id,
            "description": content[:2000],
            "source": "korchestrator-dashboard",
        }
        project_id = os.environ.get("KCG_PROJECT_ID")
        if project_id:
            properties["project_id"] = project_id
        org_id = os.environ.get("KCG_ORG_ID")
        if org_id:
            properties["org_id"] = org_id

        node = {
            "id": f"korch-decision-{self._trace_id}-{_hex_id(6)}",
            "label": "Decision",
            "properties": properties,
            "confidence_score": _DECISION_CONFIDENCE,
            "valid_from": datetime.now(timezone.utc).isoformat(),
        }
        # KCG's live /ingest handler (src/main.py) expects a *singular* {"node": {...}} body —
        # not the {"nodes": [...]} batch shape the KCG quickstart docs actually show. Confirmed by
        # direct testing: the batch shape returns {"status": "success"} but silently writes
        # nothing (the handler's `if event.node:` check is simply never true), while this shape
        # round-trips through /graph/nodes and /analytics/summary correctly.
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{_base_url()}/ingest", json={"node": node}, headers=self._headers()
                )
                if response.status_code >= 400:
                    logger.warning(
                        "kcg_tracing.export_decision_failed status=%s body=%s",
                        response.status_code,
                        response.text[:300],
                    )
        except Exception as exc:  # tracing must never break a demo run
            logger.warning("kcg_tracing.export_decision_error: %s", exc)
