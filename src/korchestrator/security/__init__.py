"""Leaf-utility layer (Shield).

Allowed imports (beyond stdlib + pydantic): config, exceptions, constants. Redacts PII, handles
secrets, and sanitises output; one consolidated Shield implementation.
"""

from korchestrator.security.redactor import RedactionResult, Shield

__all__ = ["RedactionResult", "Shield"]
