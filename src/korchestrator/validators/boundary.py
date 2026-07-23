"""Leaf-utility layer.

Imports: korchestrator.exceptions, stdlib.

Domain-rule validation Pydantic cannot express, applied at the public façade's trust boundary
(spec 08 §7): objective length, ``max_supersteps`` range, and agent-id uniqueness within a swarm.
Structural checks (types, ranges, enum membership, patterns) stay on the models themselves via
`pydantic.Field` — this module holds only what a single field's own validator cannot see.
"""

from __future__ import annotations

from collections.abc import Container

from korchestrator.exceptions import ValidationError

__all__ = ["validate_max_supersteps", "validate_objective", "validate_unique_agent_id"]

MIN_OBJECTIVE_CHARS = 10
MAX_SUPERSTEPS_BOUNDS = (1, 100)


def validate_objective(objective: str) -> None:
    """Reject an objective shorter than the minimum (spec 08 §7's public façade boundary).

    Raises:
        ValidationError: If ``objective`` has fewer than :data:`MIN_OBJECTIVE_CHARS` characters.

    Example:
        >>> from korchestrator.validators import validate_objective
        >>> validate_objective("Summarize the Q3 incident reports")  # no error
    """
    if len(objective) < MIN_OBJECTIVE_CHARS:
        raise ValidationError(
            f"Objective must be at least {MIN_OBJECTIVE_CHARS} characters, got "
            f"{len(objective)}. Describe the goal in a sentence, e.g. 'Summarize the Q3 "
            "incident reports'.",
            code="KORCH_VALIDATION_FAILED",
        )


def validate_max_supersteps(max_supersteps: int) -> None:
    """Reject a ``max_supersteps`` outside the documented bound (spec 08 §7).

    Raises:
        ValidationError: If ``max_supersteps`` is outside :data:`MAX_SUPERSTEPS_BOUNDS`.

    Example:
        >>> from korchestrator.validators import validate_max_supersteps
        >>> validate_max_supersteps(10)  # no error
    """
    low, high = MAX_SUPERSTEPS_BOUNDS
    if not low <= max_supersteps <= high:
        raise ValidationError(
            f"max_supersteps must be between {low} and {high}, got {max_supersteps}.",
            code="KORCH_VALIDATION_FAILED",
        )


def validate_unique_agent_id(agent_id: str, existing_ids: Container[str]) -> None:
    """Reject an ``agent_id`` already present in ``existing_ids`` (spec 08 §7).

    A duplicate id would otherwise silently overwrite the earlier agent (a dict keyed by id) —
    fail fast instead, at the point the second agent is declared.

    Raises:
        ValidationError: If ``agent_id`` is already in ``existing_ids``.

    Example:
        >>> from korchestrator.validators import validate_unique_agent_id
        >>> validate_unique_agent_id("lead", {"security", "perf"})  # no error
    """
    if agent_id in existing_ids:
        raise ValidationError(
            f"Duplicate agent id {agent_id!r}. Every agent in a swarm must have a unique id; "
            "give this one a different id.",
            code="KORCH_VALIDATION_FAILED",
        )
