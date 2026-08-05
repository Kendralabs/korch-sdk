"""A minimal, self-contained FastAPI router exposing one korchestrator Swarm over HTTP.

This is deliberately separate from the rest of the dashboard (`main.py`'s scenario 1-4 machinery
and `gateway.py`'s multi-provider `LiteLLMGateway`): it shows the smallest useful way to put a
real SDK swarm behind an API — build the `Swarm`, run it off the event loop, stream its events
back over SSE. Two endpoints, one in-memory run registry, no shared state with the rest of the app.

Business scenario: a customer support escalation about a failed payment, worked by four agents
on independently configurable models (triage -> researcher [tool use] -> resolver -> reviewer).
See `examples/08_support_escalation_swarm.py` for the same swarm as a standalone script — the
agent/topology definitions are intentionally duplicated here rather than imported, since that
script is a teaching artifact and this module is the production-shaped consumer.
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
from korchestrator.events import Event, EventPublisher
from korchestrator.models.state import Message, MessageRole, RunStatus
from korchestrator.providers import OpenAIGateway
from korchestrator.tools import ConnectorRegistry

try:
    from tracing import TracedGateway, tracing_enabled
except ImportError:
    from dashboard.backend.tracing import TracedGateway, tracing_enabled

try:
    from kcg_tracing import KCGTracedGateway, kcg_tracing_enabled
except ImportError:
    from dashboard.backend.kcg_tracing import KCGTracedGateway, kcg_tracing_enabled

router = APIRouter(prefix="/api/swarm/support-escalation", tags=["support-escalation"])

_DEFAULT_MODELS = {
    "triage": "gpt-4o-mini",
    "researcher": "gpt-4o-mini",
    "resolver": "gpt-4o",
    "reviewer": "gpt-4o-mini",
}

_OBJECTIVE = (
    "Handle this customer support escalation: 'My recurring subscription payment failed twice "
    "this week even though I have sufficient funds. I need this resolved today.'"
)

# run_id -> EventPublisher, isolated from main.py's own `active_runs`.
_runs: dict[str, EventPublisher] = {}


# --- Request/response models ----------------------------------------------------------------
class RunRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "objective": (
                    "Handle this customer support escalation: 'My recurring subscription "
                    "payment failed twice this week even though I have sufficient funds. I "
                    "need this resolved today.'"
                ),
                "agent_models": {
                    "triage": "gpt-4o-mini",
                    "researcher": "gpt-4o-mini",
                    "resolver": "gpt-4o",
                    "reviewer": "gpt-4o-mini",
                },
            }
        }
    )

    objective: Optional[str] = None
    agent_models: dict[str, str] = Field(default_factory=dict)


class RunResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"run_id": "support-escalation-a1b2c3d4"}}
    )

    run_id: str


# --- The one tool the researcher agent can call ---------------------------------------------
async def _lookup_account(args: dict) -> str:
    account_id = str(args.get("account_id", "unknown"))
    return (
        f"account {account_id}: card on file expired 2026-07-15; last successful payment was "
        "2026-06-02 ($89.00); 2 failed attempts this week (reason: expired_card)."
    )


_tool_registry = ConnectorRegistry().register_tool(
    "lookup_account",
    {
        "type": "object",
        "properties": {"account_id": {"type": "string"}},
        "required": ["account_id"],
    },
    _lookup_account,
    description="Look up a customer account's recent payment history by account_id.",
)


# --- Deterministic offline stand-in, used only when OPENAI_API_KEY is unset -----------------
_RESEARCH_MARKER = "card on file expired 2026-07-15"
_RESOLUTION_MARKER = "service credit"
_OFFLINE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _worker_reply(*, answer: str, is_final: bool) -> str:
    return f"[[ ## answer ## ]]\n{answer}\n\n[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"


def _react_reply(
    *, thought: str = "", tool_name: str = "", tool_args: str = "", answer: str = "", is_final: bool
) -> str:
    return (
        "[[ ## thought ## ]]\n"
        f"{thought}\n\n"
        "[[ ## tool_name ## ]]\n"
        f"{tool_name}\n\n"
        "[[ ## tool_args ## ]]\n"
        f"{tool_args}\n\n"
        "[[ ## answer ## ]]\n"
        f"{answer}\n\n"
        f"[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"
    )


class OfflineGateway:
    """Deterministic, role-aware, offline stand-in — see examples/08_support_escalation_swarm.py
    for the identical design rationale (content-marker-based waiting, not round-counting)."""

    def __init__(self) -> None:
        self._researcher_calls = 0

    async def complete(
        self, messages: list[Message], *, model: str, max_tokens: int | None = None
    ) -> Message:
        rendered = "\n".join(message.content for message in messages)
        return Message(
            id="offline-gateway",
            role=MessageRole.ASSISTANT,
            sender="assistant",
            content=self._reply_for(rendered),
            superstep=0,
            valid_time=_OFFLINE_TIME,
        )

    def _reply_for(self, rendered: str) -> str:
        if "account-researcher" in rendered:
            self._researcher_calls += 1
            if self._researcher_calls == 1:
                return _react_reply(
                    thought="I should check this account's recent payment history first.",
                    tool_name="lookup_account",
                    tool_args=json.dumps({"account_id": "ACC-48213"}),
                    is_final=False,
                )
            return _react_reply(
                thought="The account lookup answers the research question.",
                answer=(
                    f"Account ACC-48213: {_RESEARCH_MARKER}, causing both failed charges; last "
                    "successful payment was $89.00 on 2026-06-02."
                ),
                is_final=True,
            )
        if "resolution-specialist" in rendered:
            if _RESEARCH_MARKER in rendered:
                return _worker_reply(
                    answer=(
                        "Update the card on file and we will retry the payment immediately at "
                        f"no extra charge; a $10 {_RESOLUTION_MARKER} has been applied for the "
                        "inconvenience."
                    ),
                    is_final=True,
                )
            return _worker_reply(
                answer="(reviewing the account researcher's findings before drafting a resolution)",
                is_final=False,
            )
        if "qa-reviewer" in rendered:
            if _RESOLUTION_MARKER in rendered:
                return _worker_reply(
                    answer="Draft approved: accurate, empathetic, and consistent with billing policy.",
                    is_final=True,
                )
            return _worker_reply(
                answer="(awaiting the drafted resolution before review)", is_final=False
            )
        if "triage-specialist" in rendered:
            return _worker_reply(
                answer="category=billing_payment_failure; urgency=high; reason=expired card on file.",
                is_final=True,
            )
        return _worker_reply(answer="(no reply)", is_final=True)

    async def available_models(self) -> list:
        return []


def _build_gateway(run_id: str | None = None):
    api_key = os.environ.get("OPENAI_API_KEY")
    gateway = (
        OpenAIGateway(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        if api_key
        else OfflineGateway()
    )
    if tracing_enabled():
        # A fixed project name, not the shared LANGSMITH_PROJECT env var — each demo gets its own
        # LangSmith project so traces from different demos never collide into one bucket.
        gateway = TracedGateway(gateway, project="korchestrator-support-escalation-demo")
    if kcg_tracing_enabled():
        gateway = KCGTracedGateway(
            gateway, service_name="korchestrator-support-escalation-demo", run_id=run_id
        )
    return gateway


def _build_swarm(objective: str, models: dict[str, str], run_id: str | None = None) -> Swarm:
    resolved = {**_DEFAULT_MODELS, **models}
    return (
        Swarm(objective=objective, model_gateway=_build_gateway(run_id), connectors=_tool_registry)
        .add(Agent(id="triage", role="triage-specialist", model=resolved["triage"]))
        .add(
            Agent(
                id="researcher",
                role="account-researcher",
                model=resolved["researcher"],
                tools=("lookup_account",),
            )
        )
        .add(Agent(id="resolver", role="resolution-specialist", model=resolved["resolver"]))
        .add(Agent(id="reviewer", role="qa-reviewer", model=resolved["reviewer"]))
        .edges([("triage", "researcher"), ("researcher", "resolver"), ("resolver", "reviewer")])
    )


# --- Endpoints ---------------------------------------------------------------------------------
@router.post("/run", response_model=RunResponse)
async def start_run(req: RunRequest) -> RunResponse:
    run_id = f"support-escalation-{os.urandom(4).hex()}"
    publisher = EventPublisher()
    _runs[run_id] = publisher

    swarm = _build_swarm(req.objective or _OBJECTIVE, req.agent_models, run_id)

    async def on_superstep(event: Event) -> None:
        await publisher.publish(Event(name="superstep", payload=dict(event.payload), run_id=run_id))

    swarm.on("superstep", on_superstep)

    async def run_task() -> None:
        try:
            await publisher.publish(
                Event(name="status_change", payload={"status": RunStatus.RUNNING.value}, run_id=run_id)
            )
            result = await asyncio.to_thread(swarm.run, max_supersteps=8)
            resolution = next(
                (
                    m.content
                    for m in reversed(result.messages)
                    if m.sender == "reviewer" and m.kind == "answer"
                ),
                result.final_answer,
            )
            await publisher.publish(
                Event(
                    name="status_change",
                    payload={
                        "status": result.status.value,
                        "final_answer": result.final_answer,
                        "resolution": resolution,
                        "messages": [
                            {
                                "sender": m.sender,
                                "kind": m.kind,
                                "content": m.content,
                                "superstep": m.superstep,
                            }
                            for m in result.messages
                        ],
                    },
                    run_id=run_id,
                )
            )
        except Exception as exc:  # the SSE client needs a terminal event either way
            await publisher.publish(
                Event(
                    name="status_change",
                    payload={"status": RunStatus.FAILED.value, "error": str(exc)},
                    run_id=run_id,
                )
            )

    asyncio.create_task(run_task())
    return RunResponse(run_id=run_id)


@router.get("/stream/{run_id}")
async def stream_run(run_id: str) -> StreamingResponse:
    publisher = _runs.get(run_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    subscription = publisher.subscribe()

    async def event_generator():
        try:
            while True:
                event = await subscription.get()
                frame = json.dumps(
                    {"name": event.name, "payload": dict(event.payload), "run_id": event.run_id or run_id},
                    separators=(",", ":"),
                )
                yield f"data: {frame}\n\n"
                if event.name == "status_change" and event.payload.get("status") in (
                    "completed",
                    "failed",
                    "cancelled",
                ):
                    break
        except asyncio.CancelledError:
            pass
        finally:
            subscription.close()
            _runs.pop(run_id, None)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
