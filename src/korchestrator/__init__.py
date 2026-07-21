"""Korchestrator SDK — the durable, deterministic multi-agent execution kernel.

Public API surface: this is the only module users import from. The complete
``__all__`` is frozen in Phase 1 (see ``docs/specs/04-public-api.md`` §6). During
Phase 0 the package exposes only ``__version__`` (spec 11, Phase 0 public surface).
"""

from __future__ import annotations

from korchestrator.version import __version__

__all__ = ["__version__"]
