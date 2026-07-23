"""Leaf-utility layer.

Allowed imports (beyond stdlib + pydantic): exceptions. The ONLY package that reads the
environment or a ``.env`` file (both confined to ``settings.py``). Owns the single typed
``Settings`` object and the process-wide ``configure()``/``get_settings()`` accessors. Built on
``pydantic.BaseModel``, not ``pydantic-settings``, to keep the base install ``pydantic``-only
(ADR 0009, ADR 0016).
"""

from korchestrator.config.process import configure, get_settings
from korchestrator.config.settings import Settings

__all__ = ["Settings", "configure", "get_settings"]
