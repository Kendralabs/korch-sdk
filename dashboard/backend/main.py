import os
import asyncio
import logging
import threading
from typing import Any, Dict, List, Literal, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

# Load dashboard/backend/.env before anything reads os.environ (API keys, BEDROCK_MODEL_ID, etc).
load_dotenv()

# Import SDK symbols
from korchestrator import Agent, Swarm, Korch
from korchestrator.config import Settings
from korchestrator.events import Event, EventPublisher
from korchestrator.tools import ConnectorRegistry
from korchestrator.models.state import AgentState, RunStatus
from korchestrator.services.hooks import Middleware
from korchestrator.exceptions import GovernanceHaltError

# Import our custom gateway (import from same directory when run via uvicorn)
try:
    from gateway import LiteLLMGateway  # when run from backend/ directory
except ImportError:
    from dashboard.backend.gateway import LiteLLMGateway  # when run from repo root

# The support-escalation demo: a separate, self-contained router (own run registry, own SSE
# stream) added on top of the existing app without touching the scenario 1-4 code above.
try:
    from support_escalation_router import router as support_escalation_router
except ImportError:
    from dashboard.backend.support_escalation_router import (
        router as support_escalation_router,
    )

# The financial-crime investigation demo: same additive pattern as support_escalation_router.
try:
    from fincrime_router import router as fincrime_router
except ImportError:
    from dashboard.backend.fincrime_router import router as fincrime_router

# The general researcher demo: same additive pattern, single agent, no topology or HITL gate.
try:
    from researcher_router import router as researcher_router
except ImportError:
    from dashboard.backend.researcher_router import router as researcher_router


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard.main")

app = FastAPI(title="Korchestrator SDK Dashboard API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(support_escalation_router)
app.include_router(fincrime_router)
app.include_router(researcher_router)

# Global memory storage
api_keys: Dict[str, str] = {
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
    "AWS_BEARER_TOKEN_BEDROCK": os.environ.get("AWS_BEARER_TOKEN_BEDROCK", ""),
}

# Mapping of active run_id -> (EventPublisher, Task, MockHITLMiddleware | None)
active_runs: Dict[str, tuple[EventPublisher, asyncio.Task, Optional[Any]]] = {}

# Custom request models
class KeyConfigRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "openai_key": "sk-demo-REPLACE_WITH_YOUR_OPENAI_KEY",
                "anthropic_key": "sk-ant-demo-REPLACE_WITH_YOUR_ANTHROPIC_KEY",
                "bedrock_token": "demo-bedrock-bearer-token",
            }
        }
    )

    openai_key: Optional[str] = ""
    anthropic_key: Optional[str] = ""
    bedrock_token: Optional[str] = ""

class AgentInput(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "researcher",
                "role": "Researcher",
                "model": "gpt-4o-mini",
                "goal": "Find information from the web.",
                "backstory": "",
                "tools": [],
            }
        }
    )

    id: str
    role: str
    model: Optional[str] = None
    goal: Optional[str] = ""
    backstory: Optional[str] = ""
    tools: List[str] = Field(default_factory=list)

class SwarmStartRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scenario": "scenario2",
                "objective": "Write a comprehensive market analysis for the EV sector.",
                "max_supersteps": 8,
                "use_temporal": False,
                "trust_threshold": 0.5,
                "agents": [
                    {
                        "id": "researcher",
                        "role": "Researcher",
                        "model": "gpt-4o-mini",
                        "goal": "Find information from the web.",
                        "backstory": "",
                        "tools": [],
                    },
                    {
                        "id": "analyst",
                        "role": "Analyst",
                        "model": "gpt-4o-mini",
                        "goal": "Analyze collected data.",
                        "backstory": "",
                        "tools": [],
                    },
                    {
                        "id": "writer",
                        "role": "Writer",
                        "model": "gpt-4o",
                        "goal": "Produce the final report.",
                        "backstory": "",
                        "tools": [],
                    },
                ],
                "edges": [["researcher", "analyst"], ["analyst", "writer"]],
            }
        }
    )

    scenario: Literal["scenario1", "scenario2", "scenario3", "scenario4"]
    objective: str
    max_supersteps: int = 10
    use_temporal: bool = False
    trust_threshold: float = 0.5
    agents: List[AgentInput] = Field(default_factory=list)
    edges: List[List[str]] = Field(default_factory=list)

# Mock Tools for Scenario 3
async def mock_web_search(args: dict) -> str:
    query = str(args.get("query", "")).lower()
    logger.info(f"Mock Tool: web_search executing for query: {query}")
    if "acme" in query:
        return "[Tool Observation] Search result: Acme Corp revenue in 2025 was verified as $50M USD."
    return f"[Tool Observation] Search result: No relevant information found for query '{query}'."

async def mock_calculate_tax(args: dict) -> str:
    amount = float(args.get("amount", 0.0))
    rate = float(args.get("rate", 0.1))
    tax = amount * rate
    logger.info(f"Mock Tool: calculate_tax executing for amount: {amount}, rate: {rate}")
    return f"[Tool Observation] Tax Calculation: The {rate*100}% tax on {amount} is {tax}."

# Setup registry for mock tools
tool_registry = ConnectorRegistry()
tool_registry.register_tool(
    "web_search",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    mock_web_search,
    description="Search the web for corporate records and database listings.",
)
tool_registry.register_tool(
    "calculate_tax",
    {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "rate": {"type": "number"},
        },
        "required": ["amount", "rate"],
    },
    mock_calculate_tax,
    description="Calculate the tax rate amount for a given financial figure.",
)

# Custom Middleware for Local HITL Mocking
#
# "reject" raises GovernanceHaltError from before_superstep — the SDK's HookRegistry lets this one
# exception type propagate (spec 07 §9), and PregelRunner.run catches it to halt the run for real
# with RunStatus.GOVERNANCE_PAUSED, instead of the swarm computation running to completion in the
# background regardless. We also publish our own "cancelled" status_change immediately so the SSE
# stream/UI get a clearer, dashboard-specific terminal status than the SDK's generic paused one.
class LocalHITLMiddleware(Middleware):
    def __init__(self, run_id: str, threshold: float, publisher: EventPublisher) -> None:
        self.run_id = run_id
        self.threshold = threshold
        self.publisher = publisher
        # threading.Event, not asyncio.Event: before_superstep runs inside the worker thread's own
        # event loop (Swarm.run/Korch.run call asyncio.run() internally on a to_thread worker),
        # while approve/reject arrive from the main FastAPI event loop's thread. asyncio.Event is
        # bound to a single loop and is not safe to set() cross-thread; threading.Event is.
        self._resume_event = threading.Event()
        self.decision: Literal["approve", "reject"] = "approve"
        self.feedback: str = ""
        self.rejected = False

    async def before_superstep(self, state: AgentState) -> None:
        # Simulate a HITL pause in superstep 1 of Scenario 4
        # or if the running trust score falls below threshold
        if state.superstep == 1 or state.trust_score < self.threshold:
            logger.info(f"LocalHITLMiddleware: Pausing execution for run_id={self.run_id}")

            # Emit pause event to SSE client
            await self.publisher.publish(
                Event(
                    name="status_change",
                    payload={
                        "status": RunStatus.GOVERNANCE_PAUSED.value,
                        "superstep": state.superstep,
                        "trust_score": state.trust_score,
                        "message": "Execution paused. Approvals threshold triggered.",
                    },
                    run_id=self.run_id,
                )
            )

            # Block until resume_event is set via HTTP endpoints. Offloaded to a thread so the
            # worker's own event loop isn't blocked by a bare threading.Event.wait().
            await asyncio.to_thread(self._resume_event.wait)

            logger.info(f"LocalHITLMiddleware: Resumed with decision={self.decision}")
            if self.decision == "reject":
                self.rejected = True
                await self.publisher.publish(
                    Event(
                        name="status_change",
                        payload={
                            "status": RunStatus.CANCELLED.value,
                            "message": "Run rejected and halted by operator.",
                        },
                        run_id=self.run_id,
                    )
                )
                raise GovernanceHaltError(
                    self.feedback or "Run rejected and halted by operator.", run_id=self.run_id
                )

# REST Endpoints
@app.get("/api/config")
async def get_config():
    return {
        "openai_key": bool(api_keys["OPENAI_API_KEY"]),
        "anthropic_key": bool(api_keys["ANTHROPIC_API_KEY"]),
        "bedrock_token": bool(api_keys["AWS_BEARER_TOKEN_BEDROCK"]),
    }

@app.post("/api/config")
async def save_config(req: KeyConfigRequest):
    if req.openai_key:
        api_keys["OPENAI_API_KEY"] = req.openai_key
        os.environ["OPENAI_API_KEY"] = req.openai_key
    if req.anthropic_key:
        api_keys["ANTHROPIC_API_KEY"] = req.anthropic_key
        os.environ["ANTHROPIC_API_KEY"] = req.anthropic_key
    if req.bedrock_token:
        api_keys["AWS_BEARER_TOKEN_BEDROCK"] = req.bedrock_token
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = req.bedrock_token
        
    return {"status": "keys_saved"}

@app.post("/api/runs/start")
async def start_run(req: SwarmStartRequest):
    run_id = f"run-{os.urandom(4).hex()}"
    publisher = EventPublisher()
    
    # Setup custom gateway with event callback
    def on_gateway_event(name: str, payload: dict):
        # Publish LLM gateway call progress to subscription
        asyncio.create_task(
            publisher.publish(Event(name=name, payload=payload, run_id=run_id))
        )
        
    gateway = LiteLLMGateway(api_keys=api_keys, on_event=on_gateway_event)
    
    # Configure middleware and runner
    middleware_list = []
    hitl_middleware = None
    
    if req.scenario == "scenario4" and not req.use_temporal:
        hitl_middleware = LocalHITLMiddleware(
            run_id=run_id, threshold=req.trust_threshold, publisher=publisher
        )
        middleware_list.append(hitl_middleware)

    # Define run worker thread
    async def run_swarm_task():
        try:
            # Emit initial starting state
            await publisher.publish(
                Event(
                    name="status_change",
                    payload={"status": RunStatus.RUNNING.value, "objective": req.objective},
                    run_id=run_id,
                )
            )

            # Build Swarm or Korch façade based on scenario
            if req.scenario == "scenario1":
                # Tier-1 autonomous architecture
                korch = Korch(
                    model_gateway=gateway,
                    middleware=middleware_list,
                )
                
                # Setup event hook
                async def on_superstep(event: Event):
                    await publisher.publish(
                        Event(
                            name="superstep",
                            payload=dict(event.payload),
                            run_id=run_id,
                        )
                    )
                korch.on("superstep", on_superstep)
                
                # Execute blocking thread wrapper in standard event loop
                result = await asyncio.to_thread(korch.run, req.objective, max_supersteps=req.max_supersteps)
                
            elif req.scenario in ["scenario2", "scenario3", "scenario4"]:
                # Tier-2 explicit topologies
                swarm = Swarm(
                    objective=req.objective,
                    model_gateway=gateway,
                    connectors=tool_registry if req.scenario == "scenario3" else None,
                    middleware=middleware_list,
                )
                
                # Register agents
                for a in req.agents:
                    # Map tool tuples
                    agent_tools = tuple(a.tools)
                    swarm.add(
                        Agent(
                            id=a.id,
                            role=a.role,
                            model=a.model,
                            goal=a.goal,
                            backstory=a.backstory,
                            tools=agent_tools,
                        )
                    )
                
                # Register connections (edges)
                if req.edges:
                    swarm.edges([tuple(edge) for edge in req.edges])

                # Setup superstep progress hook
                async def on_superstep(event: Event):
                    # Fetch internal messages to broadcast
                    # In a real environment, we'd load the state from database or memory repo
                    await publisher.publish(
                        Event(
                            name="superstep",
                            payload=dict(event.payload),
                            run_id=run_id,
                        )
                    )
                swarm.on("superstep", on_superstep)
                
                # Execute run
                result = await asyncio.to_thread(swarm.run, max_supersteps=req.max_supersteps)

            # If the operator rejected the run during a HITL pause, the middleware already
            # published a terminal "cancelled" status_change and closed the SSE stream — don't
            # publish a second, contradictory completion event for a result the operator halted.
            if hitl_middleware is not None and hitl_middleware.rejected:
                return

            # Yield final execution message
            messages_dump = [
                {
                    "sender": m.sender,
                    "recipient": m.recipient,
                    "kind": m.kind,
                    "content": m.content,
                    "superstep": m.superstep,
                }
                for m in result.messages
            ]

            await publisher.publish(
                Event(
                    name="status_change",
                    payload={
                        "status": result.status.value,
                        "final_answer": result.final_answer,
                        "messages": messages_dump,
                        "trust_score": result.trust_score,
                    },
                    run_id=run_id,
                )
            )

        except Exception as e:
            logger.error(f"Execution failed for run={run_id}: {e}")
            await publisher.publish(
                Event(
                    name="status_change",
                    payload={"status": RunStatus.FAILED.value, "error": str(e)},
                    run_id=run_id,
                )
            )

    # Launch task in background
    task = asyncio.create_task(run_swarm_task())
    active_runs[run_id] = (publisher, task, hitl_middleware)
    
    return {"run_id": run_id}

@app.post("/api/runs/{run_id}/approve")
async def approve_run(run_id: str, feedback: Optional[str] = None):
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    _, _, hitl = active_runs[run_id]
    if hitl is None:
        raise HTTPException(status_code=400, detail="Run is not in a paused or governance state.")
        
    # Resume the blocked middleware execution
    hitl.decision = "approve"
    hitl.feedback = feedback or "Approved"
    hitl._resume_event.set()
    
    return {"status": "approved"}

@app.post("/api/runs/{run_id}/reject")
async def reject_run(run_id: str):
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    _, _, hitl = active_runs[run_id]
    if hitl is None:
        raise HTTPException(status_code=400, detail="Run is not in a paused or governance state.")
        
    hitl.decision = "reject"
    hitl._resume_event.set()
    
    return {"status": "rejected"}

@app.get("/api/runs/{run_id}/stream")
async def stream_run_events(run_id: str):
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    publisher, _, _ = active_runs[run_id]
    subscription = publisher.subscribe()

    async def event_generator():
        import json as _json
        try:
            while True:
                event = await subscription.get()
                # Send as plain SSE data (no named event: line) so the browser's
                # EventSource.onmessage fires. The JSON contains {name, payload, run_id}.
                frame = _json.dumps({
                    "name": event.name,
                    "payload": dict(event.payload),
                    "run_id": event.run_id or run_id,
                }, separators=(",", ":"))
                yield f"data: {frame}\n\n"

                if event.name == "status_change":
                    status = event.payload.get("status")
                    if status in ["completed", "failed", "cancelled"]:
                        break
        except asyncio.CancelledError:
            logger.info(f"Stream client disconnected for run_id={run_id}")
        finally:
            subscription.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
