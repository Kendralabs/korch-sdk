"""Korchestrator — durable multi-agent execution kernel.

The curated public surface: this is the only module users import from. Everything not in
``__all__`` (and not an ARI port, documented model, or the remote contract) is internal and may
change in any release. See ``docs/specs/04-public-api.md``.

The list is frozen at P1 and grows deliberately: P8 adds ``configure``, ``enable_logging``,
``from_json``, and ``to_json`` (each a MINOR addition that updates the golden snapshot). The remote
client stays behind the ``[remote]`` extra and is never imported here. ``TimeoutError`` is reachable
as ``korchestrator.exceptions.TimeoutError`` but is deliberately not re-exported at top level, so a
``from korchestrator import *`` never shadows the builtin.
"""

from korchestrator.config import Settings
from korchestrator.exceptions import (
    AuthError,
    GovernanceHaltError,
    KorchError,
    MissingExtraError,
    NetworkError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    RoutingError,
    RunFailedError,
    RunTimeoutError,
    ToolError,
    ValidationError,
)
from korchestrator.interfaces import (
    IDurableRuntime,
    IExecutionSandbox,
    IIdentityProvider,
    IModelGateway,
)
from korchestrator.models import AgentState, Message, RunResult, RunStatus, StateUpdate
from korchestrator.services import Agent, Korch, Swarm
from korchestrator.version import __version__

__all__ = [
    "Agent",
    "AgentState",
    "AuthError",
    "GovernanceHaltError",
    "IDurableRuntime",
    "IExecutionSandbox",
    "IIdentityProvider",
    "IModelGateway",
    "Korch",
    "KorchError",
    "Message",
    "MissingExtraError",
    "NetworkError",
    "ProviderError",
    "QuotaExceededError",
    "RateLimitError",
    "RoutingError",
    "RunFailedError",
    "RunResult",
    "RunStatus",
    "RunTimeoutError",
    "Settings",
    "StateUpdate",
    "Swarm",
    "ToolError",
    "ValidationError",
    "__version__",
]
