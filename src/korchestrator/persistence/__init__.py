"""Context layer (L3).

Allowed imports (beyond stdlib + pydantic): interfaces, models, config, exceptions, security,
serializers. The bitemporal Context Graph client behind GraphRepository (in-memory default
backend). ``security`` (a leaf utility) is used only for Shield redaction on the ingest path.
"""

from __future__ import annotations

from korchestrator.persistence.context_graph import ContextGraphClient
from korchestrator.persistence.factory import resolve_repository
from korchestrator.persistence.repository import InMemoryGraphRepository

__all__ = ["ContextGraphClient", "InMemoryGraphRepository", "resolve_repository"]
