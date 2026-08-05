"""Financial-crime investigation swarm — a minimal, self-contained FastAPI router.

Modeled after the shape of `support_escalation_router.py`: its own run registry, its own
`EventPublisher`, its own SSE stream, mounted additively into `main.py`. The scenario (rebuilt
from the "hsbc-fincrime" reference demo's narrative — see the plan for provenance) is a fan-out /
fan-in investigation: five specialist agents work an alert in parallel, all five findings converge
on one reconciler agent, and the reconciled assessment is held for human sign-off before it's
considered final. Fixtures live in fincrime_data.py; all data is synthetic.

Two things intentionally are NOT parsed out of the model's free text, matching how the reference
demo's own BFF worked: each agent's *finding* metadata (severity/title/tool/confidence) is a
static template keyed by agent id — only the finding's summary is the agent's real output — and
the risk grade/recommendation are computed from the set of raised severities, not regexed out of
the reconciler's prose. Free-text parsing of an LLM's exact wording is exactly the kind of thing
that breaks the moment the wording changes.
"""

import asyncio
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from korchestrator import Agent, Swarm
from korchestrator.events import Event
from korchestrator.exceptions import GovernanceHaltError
from korchestrator.models.state import AgentState, Message, MessageRole
from korchestrator.providers import OpenAIGateway
from korchestrator.services.hooks import Middleware
from korchestrator.tools import ConnectorRegistry

try:
    from tracing import TracedGateway, tracing_enabled
except ImportError:
    from dashboard.backend.tracing import TracedGateway, tracing_enabled

try:
    from fincrime_data import (
        ACTIVITY_PROFILE,
        ADVERSE_MEDIA,
        ALERT,
        CASE_HISTORY,
        COUNTERPARTIES,
        CUSTOMER,
        ENTITY_LINKS,
        KYC_DOCUMENTS,
        PEP_HITS,
        RM_DIRECTORY,
        SANCTIONS_HITS,
        TRANSACTIONS,
        UBO_CHAIN,
        WORLDCHECK_HITS,
    )
except ImportError:
    from dashboard.backend.fincrime_data import (
        ACTIVITY_PROFILE,
        ADVERSE_MEDIA,
        ALERT,
        CASE_HISTORY,
        COUNTERPARTIES,
        CUSTOMER,
        ENTITY_LINKS,
        KYC_DOCUMENTS,
        PEP_HITS,
        RM_DIRECTORY,
        SANCTIONS_HITS,
        TRANSACTIONS,
        UBO_CHAIN,
        WORLDCHECK_HITS,
    )

router = APIRouter(prefix="/api/swarm/fincrime", tags=["fincrime"])

_DEFAULT_MODELS = {
    "kyc_kyb": "gpt-4o",
    "osint_screening": "gpt-4o",
    "case_history": "gpt-4o-mini",
    "fincrime_guardian": "gpt-4o",
    "rm_liaison": "gpt-4o-mini",
    "reconciler": "gpt-4o",
}

_ROLE_LABEL = {
    "kyc_kyb": "KYC/KYB Agent",
    "osint_screening": "OSINT & Screening Agent",
    "case_history": "Case History Agent",
    "fincrime_guardian": "Transaction Analysis Agent",
    "rm_liaison": "RM Liaison Agent",
    "reconciler": "Reconciliation & Investigator Report Agent",
}

_OBJECTIVE = (
    f"Investigate {ALERT['trigger']} on {ALERT['customer']} (alert {ALERT['id']}) end-to-end: "
    "rebuild the KYC/UBO picture, screen for sanctions/PEP/adverse-media, review case history, "
    "analyze the transaction book for typologies, draft an RM information request, then "
    "reconcile all findings into one risk-graded assessment with a recommendation (escalate / "
    "request info / close). Do NOT generate a SAR. Findings will be held for human sign-off."
)

# run_id -> HITL gate, isolated from every other router's state.
_runs: dict[str, "_HitlGate"] = {}

# run_id -> every event published so far — the SSE endpoint tails this rather than subscribing to
# a push-based EventPublisher. Two reasons: (1) the run starts (via asyncio.create_task) before a
# client necessarily has its SSE GET open yet, so a push-only queue would silently drop events
# published before that subscription exists; (2) five investigator agents reason concurrently,
# each via its own asyncio.to_thread *inside* the outer asyncio.to_thread(swarm.run, ...) worker —
# cross-thread event-loop signaling (call_soon_threadsafe / run_coroutine_threadsafe) reaching back
# to the outer loop from that nesting reliably hung this process the moment a GovernanceHaltError
# (the HITL-reject path) unwound through it, confirmed in isolation without any HTTP/FastAPI layer
# involved. A plain list append is GIL-safe from any thread with no event-loop interaction at all,
# so the SSE generator below just polls it — sidesteps the failure mode entirely instead of
# tracking down the exact platform-level cause.
_event_log: dict[str, list[Event]] = {}


def _publish(run_id: str, event: Event) -> None:
    _event_log.setdefault(run_id, []).append(event)


# --- Request/response models ------------------------------------------------------------------
class RunRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "objective": _OBJECTIVE,
                "agent_models": {"kyc_kyb": "gpt-4o", "case_history": "gpt-4o-mini"},
            }
        }
    )

    objective: Optional[str] = None
    agent_models: dict[str, str] = Field(default_factory=dict)


class RunResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"run_id": "fincrime-a1b2c3d4"}})

    run_id: str


class SignoffRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"approver": "D. Alderside", "feedback": "Reviewed, proceed."}}
    )

    approver: Optional[str] = None
    feedback: Optional[str] = None


# --- Mock tools, one per source system, backed by fincrime_data.py -----------------------------
async def customer_master_lookup(args: dict) -> str:
    c = CUSTOMER
    return (
        f"{c['name']}: incorporated {c['incorporated']}; relationship since {c['relationship_since']}; "
        f"segment {c['segment']}; declared corridor {c['declared_corridor']}; "
        f"current risk rating: {c['current_risk_rating']}."
    )


async def document_store_retrieval(args: dict) -> str:
    lines = [f"{d['doc']}: {d['status']} (dated {d['date']})" for d in KYC_DOCUMENTS]
    return "KYC documents on file — " + "; ".join(lines)


async def ubo_graph_resolver(args: dict) -> str:
    return " ".join(UBO_CHAIN["chain"]) + " NOTE: " + UBO_CHAIN["note"]


async def worldcheck_one(args: dict) -> str:
    lines = [f"{h['match']} ({h['category']}, score {h['match_score']}): {h['detail']}" for h in WORLDCHECK_HITS]
    return "World-Check One hits — " + " | ".join(lines)


async def sanctions_lists(args: dict) -> str:
    lines = [f"{h['list']}: matched '{h['match']}' — {h['assessment']}" for h in SANCTIONS_HITS]
    return "Sanctions screening — " + " | ".join(lines)


async def pep_register(args: dict) -> str:
    h = PEP_HITS[0]
    return f"PEP register: {h['name_screened']} is a {h['status']} — {h['role']} ({h['domestic_or_foreign']})."


async def adverse_media_search(args: dict) -> str:
    h = ADVERSE_MEDIA[0]
    return f'Adverse media: "{h["headline"]}" — relevance {h["relevance"]}.'


async def case_management_retrieval(args: dict) -> str:
    lines = [f"{c['case_id']} ({c['status']}, {c['type']}): subject {c['subject']} — {c['note']}" for c in CASE_HISTORY]
    return "Case history — " + " | ".join(lines)


async def entity_resolution_lookup(args: dict) -> str:
    link = ENTITY_LINKS[0]
    return f"{link['entity_a']} <-> {link['entity_b']}: {link['relationship']}, linked to {link['linked_case']}."


async def transaction_feed_reader(args: dict) -> str:
    lines = [
        f"{t['id']} {t['date']} {t['direction']} ${t['amount_usd']:,} with {t['counterparty']} ({t['note']})"
        for t in TRANSACTIONS
    ]
    return "Transaction book — " + " | ".join(lines)


async def typology_classifier(args: dict) -> str:
    return (
        "Typology classification: round-tripping / layering detected — four transactions "
        "(TXN-1001..1004, ~$460k-$480k) cycle through Ashworth Capital Partners Ltd, Northgate "
        "Commercial SA and Silverline Trading FZE and return within 7-8 days, distinct from the "
        "clean baseline trade activity with Regional Cargo Distributors Ltd and Coastal Freight & Co."
    )


async def counterparty_graph(args: dict) -> str:
    lines = [f"{c['name']} ({c['jurisdiction']}): {c['role']}" for c in COUNTERPARTIES]
    return "Counterparty graph — " + " | ".join(lines)


async def activity_profile_compare(args: dict) -> str:
    p = ACTIVITY_PROFILE
    return (
        f"Declared: {p['declared_corridor']} at ~${p['declared_monthly_volume_usd']:,}/mo. "
        f"Actual: {p['actual_corridor_observed']} at ~${p['actual_monthly_volume_usd']:,}/mo. "
        f"Gap: {p['gap']}"
    )


async def rm_directory(args: dict) -> str:
    r = RM_DIRECTORY
    return f"Relationship manager for {r['customer']}: {r['relationship_manager']} ({r['team']}, {r['email']})."


async def draft_message_composer(args: dict) -> str:
    topic = str(args.get("topic") or "source of funds for the GB-CY corridor")
    return (
        f'Draft RFI to the RM: "Please obtain source-of-funds evidence from the customer for '
        f'{topic}, and confirm whether the GB-CY corridor should be added to the declared '
        'activity profile."'
    )


_TOOLS: list[tuple[str, dict, object, str]] = [
    ("customer_master_lookup", {"type": "object", "properties": {}}, customer_master_lookup, "Look up the customer's profile and current risk rating."),
    ("document_store_retrieval", {"type": "object", "properties": {}}, document_store_retrieval, "List KYC documents on file and their status."),
    ("ubo_graph_resolver", {"type": "object", "properties": {}}, ubo_graph_resolver, "Resolve the customer's ultimate-beneficial-owner chain."),
    ("worldcheck_one", {"type": "object", "properties": {}}, worldcheck_one, "Screen the UBO against World-Check One."),
    ("sanctions_lists", {"type": "object", "properties": {}}, sanctions_lists, "Screen the UBO against consolidated sanctions lists."),
    ("pep_register", {"type": "object", "properties": {}}, pep_register, "Check the UBO's politically-exposed-person status."),
    ("adverse_media_search", {"type": "object", "properties": {}}, adverse_media_search, "Search adverse media for the UBO."),
    ("case_management_retrieval", {"type": "object", "properties": {}}, case_management_retrieval, "Retrieve prior alerts and cases on this customer and related parties."),
    ("entity_resolution_lookup", {"type": "object", "properties": {}}, entity_resolution_lookup, "Resolve entity relationships (shared directors etc.)."),
    ("transaction_feed_reader", {"type": "object", "properties": {}}, transaction_feed_reader, "Read the customer's recent transaction book."),
    ("typology_classifier", {"type": "object", "properties": {}}, typology_classifier, "Classify money-laundering typologies present in the transaction book."),
    ("counterparty_graph", {"type": "object", "properties": {}}, counterparty_graph, "List the customer's counterparties and their role."),
    ("activity_profile_compare", {"type": "object", "properties": {}}, activity_profile_compare, "Compare declared vs actual activity profile."),
    ("rm_directory", {"type": "object", "properties": {}}, rm_directory, "Look up the customer's relationship manager."),
    ("draft_message_composer", {"type": "object", "properties": {"topic": {"type": "string"}}}, draft_message_composer, "Draft a message to the relationship manager."),
]


def _build_tool_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    for name, schema, fn, description in _TOOLS:
        registry.register_tool(name, schema, fn, description=description)
    return registry


# --- Findings: static per-agent template; only the summary is the model's real output ----------
_FINDING_TEMPLATES = {
    "kyc_kyb": {"id": "F-KYC-1", "severity": "high", "tool": "ubo_graph_resolver", "title": "Hidden UBO behind two offshore layers", "confidence": 0.90},
    "osint_screening": {"id": "F-SCR-1", "severity": "high", "tool": "pep_register", "title": "Confirmed PEP; sanctions hit is a false positive", "confidence": 0.88},
    "case_history": {"id": "F-CASE-1", "severity": "high", "tool": "entity_resolution_lookup", "title": "Shared director on an open TBML case", "confidence": 0.85},
    "fincrime_guardian": {"id": "F-TXN-1", "severity": "critical", "tool": "typology_classifier", "title": "Round-tripping via shell counterparties", "confidence": 0.87},
    "rm_liaison": {"id": "F-RM-1", "severity": "high", "tool": "activity_profile_compare", "title": "Undeclared GB-CY corridor; source of funds missing", "confidence": 0.86},
}

_SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1, "info": 0}


def _compute_assessment(findings: list[dict]) -> dict:
    """Deterministic risk grade + recommendation from the raised findings' severities."""
    worst = max((f["severity"] for f in findings), key=lambda s: _SEVERITY_RANK.get(s, 0), default="info")
    high_or_above = sum(1 for f in findings if _SEVERITY_RANK.get(f["severity"], 0) >= 2)
    if worst == "critical" or high_or_above >= 3:
        grade = "HIGH"
        recommendation = (
            "Escalate and place the relationship under enhanced due diligence (EDD) pending the "
            "RM's source-of-funds response. Do not close without EDD sign-off."
        )
    elif high_or_above >= 1:
        grade = "MEDIUM"
        recommendation = "Request additional information from the RM before deciding; re-review in 30 days."
    else:
        grade = "LOW"
        recommendation = "Close — no material findings; resume standard monitoring."
    return {"grade": grade, "recommendation": recommendation}


# --- Role inference + event-emitting gateway wrapper (works for real or offline) ---------------
def _infer_role(messages: list[Message]) -> str:
    rendered = "\n".join(m.content for m in messages)
    for agent_id, label in _ROLE_LABEL.items():
        if label in rendered:
            return agent_id
    return "agent"


class _EventEmittingGateway:
    """Wraps a real inner gateway to fire agent-level trace/cost events, same technique as
    gateway.py's LiteLLMGateway.on_event — kept generic here so it works over any IModelGateway."""

    def __init__(self, inner, on_event) -> None:
        self._inner = inner
        self._on_event = on_event

    async def complete(self, messages: list[Message], *, model: str, max_tokens: int | None = None) -> Message:
        agent_id = _infer_role(messages)
        started = time.monotonic()
        self._on_event("agent_status", {"agent": agent_id, "status": "active"})
        reply = await self._inner.complete(messages, model=model, max_tokens=max_tokens)
        elapsed_ms = (time.monotonic() - started) * 1000
        preview = reply.content.strip().splitlines()[0][:160] if reply.content.strip() else "(empty)"
        self._on_event("stream", {"agent": agent_id, "kind": "answer", "text": preview})
        # Token count is an ESTIMATE (≈4 chars/token) — OpenAIGateway does not return usage today.
        prompt_chars = sum(len(m.content) for m in messages)
        est_tokens = round((prompt_chars + len(reply.content)) / 4)
        self._on_event("cost", {"delta_tok": est_tokens, "delta_gbp": round(est_tokens * 0.000004, 6), "latency_ms": round(elapsed_ms)})
        return reply

    async def available_models(self) -> list:
        return await self._inner.available_models()


# --- Deterministic offline stand-in, used only when OPENAI_API_KEY is unset --------------------
_OFFLINE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

_INVESTIGATOR_MARKERS = {
    "kyc_kyb": "hidden UBO",
    "osint_screening": "CONFIRMED PEP",
    "case_history": "CASE-2026-00417",
    "fincrime_guardian": "round-tripping",
    "rm_liaison": "GB-CY corridor",
}

_INVESTIGATOR_ANSWERS = {
    "kyc_kyb": (
        "Meridian Trade Holdings Ltd's KYC review is overdue. The ownership declaration hides "
        "the hidden UBO Dimitri Kovalenko (76%) behind two offshore holding layers "
        "(Ashworth Capital Partners Ltd, Northgate Commercial SA)."
    ),
    "osint_screening": (
        "Dimitri Kovalenko is a CONFIRMED PEP (former Deputy Minister for Trade). The similarly "
        "named sanctions hit (Kovalenkov) is a false positive — DOB and jurisdiction mismatch."
    ),
    "case_history": (
        "The UBO shares a director with Northbridge Maritime Logistics Ltd, subject of the open "
        "TBML case CASE-2026-00417."
    ),
    "fincrime_guardian": (
        "Transaction analysis shows round-tripping through shell counterparties "
        "(Ashworth Capital Partners Ltd, Northgate Commercial SA, Silverline Trading FZE), "
        "distinct from clean baseline trade activity."
    ),
    "rm_liaison": (
        "Actual activity includes an undeclared GB-CY corridor with no source-of-funds evidence "
        "on file; an RFI has been drafted for the RM."
    ),
}


def _worker_reply(*, answer: str, is_final: bool) -> str:
    return f"[[ ## answer ## ]]\n{answer}\n\n[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"


def _react_reply(*, thought: str = "", tool_name: str = "", tool_args: str = "", answer: str = "", is_final: bool) -> str:
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


# Each investigator's first tool to call, plus a substring of that tool's own return value —
# once that substring shows up in the agent's own rendered context (its scratchpad, populated
# after the tool actually ran), the offline script finalizes instead of calling the tool again.
# Content-based, not a shared call counter: five investigator agents run concurrently via
# asyncio.to_thread (one real OS thread each), so any gateway-instance state shared across them
# needs to be either lock-protected or, as here, avoided — each agent only ever reads its own
# rendered prompt, which no other thread can touch.
_INVESTIGATOR_TOOL = {
    "kyc_kyb": ("ubo_graph_resolver", "Ashworth Capital Partners Ltd"),
    "osint_screening": ("pep_register", "PEP register:"),
    "case_history": ("entity_resolution_lookup", "CASE-2026-00417"),
    "fincrime_guardian": ("typology_classifier", "Typology classification"),
    "rm_liaison": ("activity_profile_compare", "Declared:"),
}


class OfflineGateway:
    """Deterministic offline stand-in. Each investigator makes one real tool call then finalizes;
    the reconciler waits (content-marker check, same technique as the support-escalation demo)
    until all five investigator markers are present in its context before finalizing."""

    async def complete(self, messages: list[Message], *, model: str, max_tokens: int | None = None) -> Message:
        rendered = "\n".join(m.content for m in messages)
        agent_id = _infer_role(messages)
        content = self._reply_for(agent_id, rendered)
        return Message(
            id="offline-gateway", role=MessageRole.ASSISTANT, sender="assistant", content=content,
            superstep=0, valid_time=_OFFLINE_TIME,
        )

    def _reply_for(self, agent_id: str, rendered: str) -> str:
        if agent_id in _INVESTIGATOR_TOOL:
            tool_name, observation_marker = _INVESTIGATOR_TOOL[agent_id]
            if observation_marker not in rendered:
                return _react_reply(thought=f"Checking {tool_name} first.", tool_name=tool_name, tool_args="{}", is_final=False)
            return _react_reply(thought="That answers the question.", answer=_INVESTIGATOR_ANSWERS[agent_id], is_final=True)
        if agent_id == "reconciler":
            seen = sum(1 for marker in _INVESTIGATOR_MARKERS.values() if marker in rendered)
            if seen >= len(_INVESTIGATOR_MARKERS):
                assessment = _compute_assessment(list(_FINDING_TEMPLATES.values()))
                return _worker_reply(
                    answer=(
                        "Reconciling all five findings: hidden UBO behind offshore layers, a "
                        "confirmed PEP, a shared director on an open TBML case, round-tripping "
                        f"transactions, and an undeclared corridor with missing source of funds. "
                        f"Risk grade {assessment['grade']}. {assessment['recommendation']}"
                    ),
                    is_final=True,
                )
            return _worker_reply(answer="(consolidating agent findings)", is_final=False)
        return _worker_reply(answer="(no reply)", is_final=True)

    async def available_models(self) -> list:
        return []


def _build_gateway(on_event) -> object:
    api_key = os.environ.get("OPENAI_API_KEY")
    inner = (
        OpenAIGateway(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        if api_key
        else OfflineGateway()
    )
    if tracing_enabled():
        # A fixed project name, not the shared LANGSMITH_PROJECT env var — each demo gets its own
        # LangSmith project so traces from different demos never collide into one bucket.
        inner = TracedGateway(inner, project="korchestrator-fincrime-demo")
    return _EventEmittingGateway(inner, on_event)


# --- HITL sign-off gate: same proven pattern as main.py's LocalHITLMiddleware ------------------
class _HitlGate(Middleware):
    """Pauses before superstep 1 — after the five investigators have their findings, before the
    reconciler synthesizes them — for human sign-off, mirroring the reference demo's SHIELD gate.

    threading.Event, not asyncio.Event: before_superstep runs inside swarm.run()'s own worker
    thread/event loop (main.py's run_task calls it via asyncio.to_thread), while the HTTP
    approve/reject handler runs on the main FastAPI event loop's thread. threading.Event is safe
    to set() across threads; asyncio.Event is bound to one loop and is not (proven in main.py).

    Known SDK-level issue (not this router's code): rejecting — i.e. `before_superstep` raising
    `GovernanceHaltError` — reliably hangs `Swarm.run()` when it's invoked via
    `asyncio.to_thread` (or a plain background `threading.Thread`) from a process that *also* has
    an asyncio event loop already running elsewhere (exactly the FastAPI/uvicorn shape this
    router runs under). Confirmed in isolation, independent of this file: a bare script driving
    the identical swarm+gate+reject with no HTTP layer at all hangs the same way the instant an
    outer `asyncio.run(...)`/running loop exists in the process, while the *exact same call*
    returns in under a second when made synchronously with no outer loop present. Approving does
    not hit this — only the raised-exception (reject) path does. `run_task` below wraps the call
    in `asyncio.wait_for(...)` so a production run can never hang indefinitely on this; it will
    reach `run_completed` with `status: "failed"` (timeout) rather than silently stalling the SSE
    stream forever.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._resume_event = threading.Event()
        self.decision: Optional[str] = None
        self.feedback = ""

    async def before_superstep(self, state: AgentState) -> None:
        if state.superstep != 1:
            return
        _publish(
            self.run_id,
            Event(name="human_request", payload={"approver": "Compliance Reviewer", "role": "Sign-off required"}, run_id=self.run_id),
        )
        await asyncio.to_thread(self._resume_event.wait)
        if self.decision == "reject":
            _publish(
                self.run_id,
                Event(name="resolved", payload={"outcome": "Rejected — investigation halted for rework."}, run_id=self.run_id),
            )
            raise GovernanceHaltError(self.feedback or "Rejected by reviewer.", run_id=self.run_id)
        _publish(
            self.run_id,
            Event(name="resolved", payload={"outcome": f"Approved by {self.feedback or 'reviewer'} — reconciling."}, run_id=self.run_id),
        )

    def resolve(self, decision: str, feedback: str) -> None:
        self.decision = decision
        self.feedback = feedback
        self._resume_event.set()


def _build_swarm(
    objective: str,
    models: dict[str, str],
    gateway,
    registry: ConnectorRegistry,
    hitl: Optional["_HitlGate"],
) -> Swarm:
    """Build the 6-agent investigation swarm. ``hitl=None`` skips the sign-off gate entirely —
    used by the performance test, which needs runs that don't block on human approval."""
    resolved = {**_DEFAULT_MODELS, **models}
    middleware = [hitl] if hitl is not None else []
    swarm = Swarm(objective=objective, model_gateway=gateway, connectors=registry, middleware=middleware)
    investigator_tools = {
        "kyc_kyb": ("customer_master_lookup", "document_store_retrieval", "ubo_graph_resolver"),
        "osint_screening": ("worldcheck_one", "sanctions_lists", "pep_register", "adverse_media_search"),
        "case_history": ("case_management_retrieval", "entity_resolution_lookup"),
        "fincrime_guardian": ("transaction_feed_reader", "typology_classifier", "counterparty_graph"),
        "rm_liaison": ("activity_profile_compare", "rm_directory", "draft_message_composer"),
    }
    for agent_id, tools in investigator_tools.items():
        swarm.add(Agent(id=agent_id, role=_ROLE_LABEL[agent_id], model=resolved[agent_id], tools=tools, max_react_steps=4))
    swarm.add(Agent(id="reconciler", role=_ROLE_LABEL["reconciler"], model=resolved["reconciler"]))
    swarm.edges([(agent_id, "reconciler") for agent_id in investigator_tools])
    return swarm


_STAGES = ["collect", "understand", "assess", "report"]


# --- Endpoints -----------------------------------------------------------------------------
@router.post("/run", response_model=RunResponse)
async def start_run(req: RunRequest) -> RunResponse:
    run_id = f"fincrime-{os.urandom(4).hex()}"
    hitl = _HitlGate(run_id)
    _runs[run_id] = hitl
    _event_log[run_id] = []

    # Plain thread-safe append — no event-loop crossing at all (see _publish's docstring above).
    # Called from whichever agent thread's gateway.complete() just returned.
    def on_event(name: str, payload: dict) -> None:
        _publish(run_id, Event(name=name, payload=payload, run_id=run_id))

    gateway = _build_gateway(on_event)
    registry = _build_tool_registry()
    swarm = _build_swarm(req.objective or _OBJECTIVE, req.agent_models, gateway, registry, hitl)

    async def on_superstep(event: Event) -> None:
        superstep_n = event.payload.get("superstep", 0)
        _publish(run_id, Event(name="superstep", payload=dict(event.payload), run_id=run_id))
        stage = _STAGES[min(int(superstep_n), len(_STAGES) - 1)]
        _publish(run_id, Event(name="stage", payload={"stage": stage}, run_id=run_id))

    swarm.on("superstep", on_superstep)

    async def run_task() -> None:
        try:
            _publish(run_id, Event(name="run_started", payload={"run_id": run_id}, run_id=run_id))
            _publish(run_id, Event(name="stage", payload={"stage": "collect"}, run_id=run_id))

            # wait_for, not a bare await: see _HitlGate's docstring — the reject path has a known
            # SDK-level hang risk under this exact (asyncio.to_thread + already-running outer
            # loop) shape. This bounds it so a rejected run always reaches run_completed instead
            # of stalling the SSE stream forever; the (unkillable) worker thread is abandoned.
            result = await asyncio.wait_for(asyncio.to_thread(swarm.run, max_supersteps=8), timeout=90)

            findings = []
            for agent_id, template in _FINDING_TEMPLATES.items():
                summary = next(
                    (m.content for m in reversed(result.messages) if m.sender == agent_id and m.kind == "answer"),
                    "",
                )
                finding = {**template, "agent": agent_id, "summary": summary}
                findings.append(finding)
                _publish(run_id, Event(name="finding", payload=finding, run_id=run_id))

            assessment = _compute_assessment(findings)
            reconciler_answer = next(
                (m.content for m in reversed(result.messages) if m.sender == "reconciler" and m.kind == "answer"),
                "",
            )
            _publish(
                run_id,
                Event(
                    name="assessment",
                    payload={"grade": assessment["grade"], "why": reconciler_answer, "recommendation": assessment["recommendation"]},
                    run_id=run_id,
                ),
            )
            _publish(run_id, Event(name="stage", payload={"stage": "report"}, run_id=run_id))
            _publish(
                run_id,
                Event(name="run_completed", payload={"status": result.status.value, "findings": findings}, run_id=run_id),
            )
        except TimeoutError:
            _publish(
                run_id,
                Event(
                    name="run_completed",
                    payload={"status": "failed", "error": "Timed out waiting for the swarm to finish (see _HitlGate docstring)."},
                    run_id=run_id,
                ),
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


@router.post("/{run_id}/approve")
async def approve_run(run_id: str, req: SignoffRequest) -> dict:
    hitl = _runs.get(run_id)
    if hitl is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    hitl.resolve("approve", req.approver or "reviewer")
    return {"status": "approved"}


@router.post("/{run_id}/reject")
async def reject_run(run_id: str, req: SignoffRequest) -> dict:
    hitl = _runs.get(run_id)
    if hitl is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    hitl.resolve("reject", req.feedback or "Rejected by reviewer.")
    return {"status": "rejected"}
