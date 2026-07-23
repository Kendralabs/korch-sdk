"""Contract layer.

Allowed imports (beyond stdlib + pydantic): types, constants. Defines the Pydantic domain
models exchanged across every boundary. All models are frozen and forbid extra fields.
"""

from korchestrator.models.agent import AgentConfig, AgentDescriptor, AgentPersona
from korchestrator.models.context_graph import DecisionNode, EventNode, GraphNode
from korchestrator.models.plan import ExecutionPlan, TaskDecomposition
from korchestrator.models.remote import (
    ApiKey,
    ApiKeySummary,
    CallerIdentity,
    Quota,
    RemoteRunResult,
    RunEvent,
    RunSummary,
)
from korchestrator.models.result import RunResult
from korchestrator.models.routing import (
    ModelCard,
    RoutingContext,
    RoutingResult,
    TaskSemantics,
)
from korchestrator.models.state import (
    AgentState,
    Message,
    MessageRole,
    Performative,
    RunStatus,
    StateUpdate,
)
from korchestrator.models.tool import ToolResult

__all__ = [
    "AgentConfig",
    "AgentDescriptor",
    "AgentPersona",
    "AgentState",
    "ApiKey",
    "ApiKeySummary",
    "CallerIdentity",
    "DecisionNode",
    "EventNode",
    "ExecutionPlan",
    "GraphNode",
    "Message",
    "MessageRole",
    "ModelCard",
    "Performative",
    "Quota",
    "RemoteRunResult",
    "RoutingContext",
    "RoutingResult",
    "RunEvent",
    "RunResult",
    "RunStatus",
    "RunSummary",
    "StateUpdate",
    "TaskDecomposition",
    "TaskSemantics",
    "ToolResult",
]
