"""Integration layer.

Allowed imports (beyond stdlib + pydantic): models, exceptions. Transforms agent-to-agent
handoffs into typed directed messages.
"""

from korchestrator.a2a.handoff import HandoffTransformer, directed_message

__all__ = ["HandoffTransformer", "directed_message"]
