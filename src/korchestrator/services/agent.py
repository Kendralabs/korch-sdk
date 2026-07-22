"""Façade layer. Imports: korchestrator.agents.

``Agent`` re-exported at its spec 04 §7 import path. The class is defined once in
``korchestrator.agents.base`` (its canonical home in the cognitive layer) and re-exported here so
``from korchestrator.services import Agent`` and ``from korchestrator import Agent`` keep working —
the same object, reachable from ``korchestrator.agents`` too (spec 07 §4). See ADR 0012.
"""

from korchestrator.agents.base import Agent

__all__ = ["Agent"]
