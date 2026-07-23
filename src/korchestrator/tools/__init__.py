"""Integration layer (L4).

Allowed imports (beyond stdlib + pydantic): interfaces, models, config, exceptions, security,
telemetry, logging. The Agent Utility Bridge: connector registry, schema validation, timeouts,
rate limits, and the Shield gate.

Public surface (spec 07 §6): ``AUBConnector`` (the execution protocol, defined in ``interfaces``
and re-exported here as the documented import path), ``Connector``, ``ConnectorRegistry``,
``invoke_tool``, the built-in connectors, and the rate-limiter contract.
"""

from korchestrator.interfaces import AUBConnector
from korchestrator.tools._ratelimit import RateLimiter, TokenBucketRateLimiter
from korchestrator.tools.bridge import Redactor, RegistryToolInvoker, invoke_tool
from korchestrator.tools.connectors import Connector, FilesystemConnector, MockSearchConnector
from korchestrator.tools.registry import ENTRY_POINT_GROUP, ConnectorRegistry

__all__ = [
    "ENTRY_POINT_GROUP",
    "AUBConnector",
    "Connector",
    "ConnectorRegistry",
    "FilesystemConnector",
    "MockSearchConnector",
    "RateLimiter",
    "Redactor",
    "RegistryToolInvoker",
    "TokenBucketRateLimiter",
    "invoke_tool",
]
