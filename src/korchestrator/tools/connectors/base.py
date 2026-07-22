"""Integration layer (L4). Imports: interfaces.

The :class:`Connector` structural contract, defined in ``interfaces`` (so ``tools`` and ``mcp`` can
share it without importing each other) and re-exported here as the documented tools import path.
"""

from korchestrator.interfaces import Connector

__all__ = ["Connector"]
