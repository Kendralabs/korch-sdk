"""Unit tests for the minimal JSON-Schema argument validator (P6.2)."""

from __future__ import annotations

from korchestrator.tools._schema import validate_args

_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "n": {"type": "integer"}, "ok": {"type": "boolean"}},
    "required": ["name"],
    "additionalProperties": False,
}


def test_valid_arguments_pass() -> None:
    assert validate_args(_SCHEMA, {"name": "x", "n": 3, "ok": True}) == []


def test_missing_required_is_reported() -> None:
    errors = validate_args(_SCHEMA, {"n": 3})
    assert any("required" in e and "name" in e for e in errors)


def test_wrong_type_is_reported() -> None:
    assert validate_args(_SCHEMA, {"name": 1}) == ["argument 'name' must be string, got int"]


def test_bool_is_not_an_integer() -> None:
    # isinstance(True, int) is True in Python, but a bool is not a JSON integer.
    assert validate_args(_SCHEMA, {"name": "x", "n": True}) == [
        "argument 'n' must be integer, got bool"
    ]


def test_additional_properties_rejected_when_forbidden() -> None:
    errors = validate_args(_SCHEMA, {"name": "x", "extra": 1})
    assert any("extra" in e for e in errors)


def test_unknown_schema_keywords_are_permissive() -> None:
    # A property with no recognised type constraint is accepted.
    assert validate_args({"type": "object", "properties": {"a": {}}}, {"a": [1, 2]}) == []
