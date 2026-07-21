"""Adapter layer.

Allowed imports (beyond stdlib + pydantic): interfaces, models, config, exceptions, logging;
provider clients optional (lazy). The default ARI implementations: local identity/sandbox,
OpenAI-compatible gateway, MockLM.
"""

__all__: list[str] = []
