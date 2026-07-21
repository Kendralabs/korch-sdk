"""Leaf-utility layer.

Allowed imports (beyond stdlib + pydantic): exceptions. The ONLY package that reads the
environment (via os.environ, confined here). Owns the single typed Settings object. Built on
pydantic.BaseModel, not pydantic-settings, to keep the base install pydantic-only (ADR 0009).
"""

from korchestrator.config.settings import Settings

__all__ = ["Settings"]
