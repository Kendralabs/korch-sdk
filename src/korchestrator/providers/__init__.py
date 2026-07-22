"""Adapter layer.

Allowed imports (beyond stdlib + pydantic): interfaces, models, config, exceptions, logging;
provider clients optional (lazy). The default ARI implementations: local identity/sandbox,
OpenAI-compatible gateway, MockLM.
"""

from korchestrator.providers.identity_local import LocalIdentityProvider
from korchestrator.providers.mock_lm import MockCall, MockLM
from korchestrator.providers.sandbox_local import LocalSandbox

__all__ = ["LocalIdentityProvider", "LocalSandbox", "MockCall", "MockLM"]
