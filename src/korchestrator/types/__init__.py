"""Leaf-utility layer.

Allowed imports (beyond stdlib + pydantic): typing_extensions (a pydantic dependency, base
install). Holds shared type aliases, TypedDicts and non-ARI Protocols exchanged across the package.
"""

from __future__ import annotations

from typing_extensions import TypeAliasType

__all__ = ["JSONValue"]

# The recursive JSON value type used by every model field that carries free-form structured data
# (context, metadata, tool output). Kept deliberately narrow — JSON-serialisable only.
#
# Defined with ``TypeAliasType`` (PEP 695) rather than the plain ``X | Y`` alias in spec 05 §3:
# pydantic v2 resolves a named recursive alias but recurses infinitely on an inline recursive
# union. The type is identical; only the definition mechanism differs.
JSONValue = TypeAliasType(
    "JSONValue",
    "str | int | float | bool | list[JSONValue] | dict[str, JSONValue] | None",
)
