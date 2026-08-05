"""A single general-purpose research/knowledge-query agent — a minimal FastAPI router.

The simplest possible member of this family of demos (see support_escalation_router.py and
fincrime_router.py for the same shape at higher complexity): one agent, no tools, no topology,
no HITL gate — just "ask a question, get an answer" over the SDK's Swarm/Agent primitives. Own
run registry, own thread-safe event buffer (same design as fincrime_router.py's, since a single
short-lived agent has no reason to need anything richer), no shared state with the other routers.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from korchestrator import Agent, Swarm
from korchestrator.events import Event
from korchestrator.models.state import Message, MessageRole
from korchestrator.providers import OpenAIGateway

try:
    from tracing import TracedGateway, tracing_enabled
except ImportError:
    from dashboard.backend.tracing import TracedGateway, tracing_enabled

router = APIRouter(prefix="/api/swarm/researcher", tags=["researcher"])

_DEFAULT_MODEL = "gpt-4o-mini"
_ROLE = "General Research & Knowledge Agent"

_DEFAULT_QUESTION = "What is the difference between durable execution and a plain retry loop?"

# run_id -> every event published so far; the SSE endpoint polls this (same pattern and rationale
# as fincrime_router.py's _event_log — plain thread-safe append, no event-loop crossing at all).
_runs: dict[str, bool] = {}
_event_log: dict[str, list[Event]] = {}


def _publish(run_id: str, event: Event) -> None:
    _event_log.setdefault(run_id, []).append(event)


class RunRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"question": _DEFAULT_QUESTION, "model": "gpt-4o-mini"}}
    )

    question: Optional[str] = None
    model: Optional[str] = None


class RunResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"run_id": "researcher-a1b2c3d4"}})

    run_id: str


_OFFLINE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


class OfflineGateway:
    """Deterministic offline stand-in, used only when OPENAI_API_KEY is unset (T1/T4)."""

    async def complete(self, messages: list[Message], *, model: str, max_tokens: int | None = None) -> Message:
        return Message(
            id="offline-gateway",
            role=MessageRole.ASSISTANT,
            sender="assistant",
            content=(
                "[[ ## answer ## ]]\nDurable execution replays a workflow's full event history "
                "to rebuild state deterministically after a crash, so it resumes exactly where it "
                "left off; a plain retry loop just re-runs the whole operation from scratch and "
                "has no memory of partial progress.\n\n[[ ## is_final ## ]]\nTrue\n\n[[ ## completed ## ]]"
            ),
            superstep=0,
            valid_time=_OFFLINE_TIME,
        )

    async def available_models(self) -> list:
        return []


def _build_gateway():
    api_key = os.environ.get("OPENAI_API_KEY")
    gateway = (
        OpenAIGateway(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        if api_key
        else OfflineGateway()
    )
    if tracing_enabled():
        gateway = TracedGateway(gateway, project="korchestrator-researcher-demo")
    return gateway


def _build_swarm(question: str, model: str) -> Swarm:
    return Swarm(objective=question, model_gateway=_build_gateway()).add(
        Agent(id="researcher", role=_ROLE, model=model)
    )


@router.post("/run", response_model=RunResponse)
async def start_run(req: RunRequest) -> RunResponse:
    run_id = f"researcher-{os.urandom(4).hex()}"
    _runs[run_id] = True
    _event_log[run_id] = []

    swarm = _build_swarm(req.question or _DEFAULT_QUESTION, req.model or _DEFAULT_MODEL)

    async def run_task() -> None:
        try:
            _publish(run_id, Event(name="run_started", payload={"run_id": run_id}, run_id=run_id))
            result = await asyncio.wait_for(asyncio.to_thread(swarm.run, max_supersteps=3), timeout=60)
            answer = next(
                (m.content for m in reversed(result.messages) if m.sender == "researcher" and m.kind == "answer"),
                result.final_answer,
            )
            _publish(
                run_id,
                Event(
                    name="run_completed",
                    payload={"status": result.status.value, "answer": answer},
                    run_id=run_id,
                ),
            )
        except TimeoutError:
            _publish(
                run_id,
                Event(name="run_completed", payload={"status": "failed", "error": "Timed out."}, run_id=run_id),
            )
        except Exception as exc:
            _publish(run_id, Event(name="run_completed", payload={"status": "failed", "error": str(exc)}, run_id=run_id))

    asyncio.create_task(run_task())
    return RunResponse(run_id=run_id)


def _frame(event: Event, run_id: str) -> str:
    payload = json.dumps(
        {"name": event.name, "payload": dict(event.payload), "run_id": event.run_id or run_id},
        separators=(",", ":"),
    )
    return f"data: {payload}\n\n"


_POLL_INTERVAL_SECONDS = 0.15


@router.get("/stream/{run_id}")
async def stream_run(run_id: str) -> StreamingResponse:
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found.")

    async def event_generator():
        sent = 0
        try:
            while True:
                buffered = _event_log.get(run_id, [])
                if sent < len(buffered):
                    for event in buffered[sent:]:
                        yield _frame(event, run_id)
                        if event.name == "run_completed":
                            return
                    sent = len(buffered)
                else:
                    await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            pass
        finally:
            _runs.pop(run_id, None)
            _event_log.pop(run_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
