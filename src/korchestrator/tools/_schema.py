"""Integration layer (L4). Imports: types, stdlib.

A minimal JSON-Schema argument validator — the object-subset the AUB needs (``type``, ``required``,
``properties`` types, ``additionalProperties``) so the base install needs no ``jsonschema``
dependency. The bridge validates a connector's arguments against its ``schema`` before ``execute``.
"""

from __future__ import annotations

from collections.abc import Mapping

from korchestrator.types import JSONValue

__all__ = ["validate_args"]

# JSON-Schema type name → the Python types that satisfy it. ``bool`` is excluded from the numeric
# types (a bool is an int in Python, but not a JSON number/integer).
_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


def validate_args(schema: Mapping[str, JSONValue], args: Mapping[str, JSONValue]) -> list[str]:
    """Return a list of validation errors for ``args`` against ``schema`` (empty means valid).

    Supports the object subset: ``required`` keys, per-property ``type``, and
    ``additionalProperties: false``. Unrecognised schema keywords are ignored (permissive).

    Args:
        schema: A JSON-Schema object describing the tool's arguments.
        args: The arguments to validate.

    Returns:
        Human-readable error messages; an empty list means the arguments are valid.

    Example:
        >>> from korchestrator.tools._schema import validate_args
        >>> schema = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}
        >>> validate_args(schema, {"n": 3})
        []
        >>> validate_args(schema, {"n": "x"})
        ["argument 'n' must be integer, got str"]
    """
    errors: list[str] = []
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    if isinstance(required, list):
        for key in required:
            if key not in args:
                errors.append(f"missing required argument {key!r}")
    if isinstance(properties, dict):
        for key, value in args.items():
            spec = properties.get(key)
            if isinstance(spec, dict):
                errors.extend(_check_type(key, spec, value))
        if schema.get("additionalProperties") is False:
            for key in args:
                if key not in properties:
                    errors.append(f"unexpected argument {key!r}")
    return errors


def _check_type(key: str, spec: Mapping[str, JSONValue], value: JSONValue) -> list[str]:
    expected = spec.get("type")
    if not isinstance(expected, str) or expected not in _TYPES:
        return []
    allowed = _TYPES[expected]
    # bool must not satisfy integer/number even though isinstance(True, int) is True.
    if isinstance(value, bool) and expected in {"integer", "number"}:
        return [f"argument {key!r} must be {expected}, got bool"]
    if not isinstance(value, allowed):
        return [f"argument {key!r} must be {expected}, got {type(value).__name__}"]
    return []
