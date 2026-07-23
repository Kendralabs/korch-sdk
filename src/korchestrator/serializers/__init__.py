"""Leaf-utility layer.

Allowed imports (beyond stdlib + pydantic): models, exceptions, constants. Round-trips domain
models to/from JSON, deterministically and version-tagged (spec 08 §6). Supports ``AgentState``,
``ExecutionPlan``, ``ModelCard``, and ``RunResult``; ``AgentGraph`` is deliberately excluded
(ADR 0017).
"""

from korchestrator.serializers.codec import from_json, to_json

__all__ = ["from_json", "to_json"]
