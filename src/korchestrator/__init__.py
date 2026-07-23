"""Korchestrator — durable multi-agent execution kernel.

The curated public surface: this is the only module users import from. Everything not in
``__all__`` (and not an ARI port, documented model, or the remote contract) is internal and may
change in any release. See ``docs/specs/04-public-api.md``.

The list is frozen at P1 and grew deliberately through P8: ``configure`` (P8.1), ``enable_logging``
(P8.3), and ``from_json``/``to_json`` (P8.5) — each a MINOR addition that updated the golden
snapshot. The remote client stays behind the ``[remote]`` extra and is never imported here.
``TimeoutError`` is reachable as ``korchestrator.exceptions.TimeoutError`` but is deliberately not
re-exported at top level, so a ``from korchestrator import *`` never shadows the builtin —
``ConfigurationError`` gets the same treatment (spec 04 §6, ADR 0016): reachable via
``korchestrator.exceptions.ConfigurationError``, not re-exported here. ``disable_logging`` gets the
same treatment too — reachable via ``korchestrator.logging.disable_logging``, matching spec 04 §6's
`__init__.py` example, which imports only ``enable_logging``.
"""

from korchestrator.config import Settings, configure
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
from korchestrator.logging import enable_logging
from korchestrator.models import AgentState, Message, RunResult, RunStatus, StateUpdate
from korchestrator.serializers import from_json, to_json
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
    "configure",
    "enable_logging",
    "from_json",
    "to_json",
]
