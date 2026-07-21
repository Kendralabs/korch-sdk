"""Contract layer.

Allowed imports (beyond stdlib + pydantic): types, constants. Defines the Pydantic domain
models exchanged across every boundary. All models are frozen and forbid extra fields.
"""

from korchestrator.models.agent import AgentConfig, AgentDescriptor, AgentPersona
from korchestrator.models.plan import ExecutionPlan, TaskDecomposition
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
    "ExecutionPlan",
    "Message",
    "MessageRole",
    "ModelCard",
    "Performative",
    "RoutingContext",
    "RoutingResult",
    "RunResult",
    "RunStatus",
    "StateUpdate",
    "TaskDecomposition",
    "TaskSemantics",
    "ToolResult",
]
