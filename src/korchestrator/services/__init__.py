"""Facade layer, the composition root.

Allowed imports (beyond stdlib + pydantic): every korchestrator module. Composes the object
graph and exposes the Korch / Swarm / Agent facade. The one wiring site.
"""

from korchestrator.services.agent import Agent
from korchestrator.services.hooks import HookRegistry, Middleware
from korchestrator.services.korch import Korch
from korchestrator.services.swarm import Swarm

__all__ = ["Agent", "HookRegistry", "Korch", "Middleware", "Swarm"]
