"""Tier 4 — the optional remote client (spec 04 §2, §7).

Layer: leaf re-export. Allowed imports: korchestrator.clients only.

Never imported by ``korchestrator/__init__.py`` — importing it eagerly would pull ``httpx`` into
the base install (spec 04 §7 intro). Reach it explicitly: ``from korchestrator.remote import
KorchestratorClient``. Requires the ``[remote]`` extra.
"""

from __future__ import annotations

from korchestrator.clients import KorchestratorClient

__all__ = ["KorchestratorClient"]
