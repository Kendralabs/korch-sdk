"""Client layer.

Allowed imports (beyond stdlib + pydantic): models, exceptions, config; httpx ([remote] extra).
The remote HTTP client, re-exported as korchestrator.remote.
"""

from korchestrator.clients.client import KorchestratorClient

__all__ = ["KorchestratorClient"]
