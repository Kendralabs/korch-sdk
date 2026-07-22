"""Integration layer (L4).

Built-in AUB connectors and the :class:`Connector` structural contract. Allowed imports:
interfaces, models, constants, types, stdlib. Each connector is a single named tool; the bridge
owns validation, timeout, rate limiting, and redaction.
"""

from korchestrator.tools.connectors.base import Connector
from korchestrator.tools.connectors.filesystem import FilesystemConnector
from korchestrator.tools.connectors.search import MockSearchConnector

__all__ = ["Connector", "FilesystemConnector", "MockSearchConnector"]
