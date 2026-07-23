"""Context layer (L3).

Allowed imports (beyond stdlib + pydantic): interfaces, models, config, exceptions,
serializers. The bitemporal Context Graph client behind GraphRepository (in-memory default
backend).
"""

from __future__ import annotations

from korchestrator.persistence.factory import resolve_repository
from korchestrator.persistence.repository import InMemoryGraphRepository

__all__ = ["InMemoryGraphRepository", "resolve_repository"]
