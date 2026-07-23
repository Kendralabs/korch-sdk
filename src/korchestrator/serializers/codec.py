"""Leaf-utility layer.

Imports: korchestrator.models, korchestrator.exceptions, korchestrator.version, pydantic, stdlib
(json).

Deterministic, version-tagged JSON round-trip for the SDK's serializable domain models
(spec 08 §6): ``AgentState``, ``ExecutionPlan``, ``ModelCard``, and ``RunResult``. ``AgentGraph``
is deliberately excluded — its nodes carry live, non-serialisable compute callables (ADR 0017).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from korchestrator.exceptions import ValidationError
from korchestrator.models.plan import ExecutionPlan
from korchestrator.models.result import RunResult
from korchestrator.models.routing import ModelCard
from korchestrator.models.state import AgentState
from korchestrator.version import __version__

__all__ = ["from_json", "to_json"]

T = TypeVar("T", bound=BaseModel)

# The current schema version for each serializable model — the single source of truth to_json/
# from_json consult. AgentState/ExecutionPlan/RunResult additionally carry their own
# `schema_version` field (existing since P1/P2, part of their own shape); ModelCard does not, so
# it is versioned here instead. One entry per supported type.
_CURRENT_SCHEMA_VERSION: dict[type[BaseModel], int] = {
    AgentState: 1,
    ExecutionPlan: 1,
    ModelCard: 1,
    RunResult: 1,
}

# A migration upgrades one model's envelope `data` dict from schema_version N to N+1. Empty today
# — nothing has evolved past v1 yet — but from_json already applies whatever is registered here in
# sequence (spec 08 §6.5), so the first real migration is a pure data change, not a new mechanism.
MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]
_MIGRATIONS: dict[tuple[type[BaseModel], int], MigrationFn] = {}


def _supported_names() -> str:
    return ", ".join(sorted(t.__name__ for t in _CURRENT_SCHEMA_VERSION))


def to_json(model: BaseModel) -> str:
    """Serialise ``model`` to a deterministic, version-tagged JSON envelope (spec 08 §6).

    Keys are sorted (recursively, at every nesting level), separators are fixed (``","``,
    ``":"``), and the output is UTF-8 with no ASCII-escaping — the same model always produces
    byte-identical output. Timestamps come out ISO-8601 with an explicit UTC offset and
    microsecond precision (pydantic's own JSON mode); floats keep their ``repr`` round-trip
    fidelity.

    Args:
        model: An instance of a supported model — currently :class:`~korchestrator.models.state.
            AgentState`, :class:`~korchestrator.models.plan.ExecutionPlan`,
            :class:`~korchestrator.models.routing.ModelCard`, or
            :class:`~korchestrator.models.result.RunResult`. ``AgentGraph`` is not supported
            (ADR 0017).

    Returns:
        The JSON envelope: ``{"schema_version", "korchestrator_version", "type", "data"}``.

    Raises:
        ValidationError: If ``model``'s type is not one of the supported models.

    Example:
        >>> from datetime import datetime, timezone
        >>> from korchestrator.models.state import AgentState
        >>> from korchestrator.serializers import to_json
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report",
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> payload = to_json(state)
        >>> to_json(state) == payload  # deterministic: same object, same bytes, every time
        True
    """
    model_type = type(model)
    if model_type not in _CURRENT_SCHEMA_VERSION:
        raise ValidationError(
            f"{model_type.__name__} is not a serializable model. Supported: "
            f"{_supported_names()}. (AgentGraph is deliberately excluded — ADR 0017.)",
            code="KORCH_VALIDATION_FAILED",
        )
    envelope = {
        "schema_version": _CURRENT_SCHEMA_VERSION[model_type],
        "korchestrator_version": __version__,
        "type": model_type.__name__,
        "data": model.model_dump(mode="json"),
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def from_json(payload: str, model_cls: type[T]) -> T:
    """Deserialise ``payload`` into ``model_cls``, applying migrations as needed (spec 08 §6.5).

    Args:
        payload: A JSON envelope produced by :func:`to_json`.
        model_cls: The expected model type.

    Returns:
        The reconstructed, validated instance.

    Raises:
        ValidationError: If ``model_cls`` is not supported, ``payload`` is not well-formed JSON,
            is not a korchestrator envelope, names a different type, carries a
            ``schema_version`` newer than this package supports, is missing a migration needed
            to reach the current version, or the migrated data fails ``model_cls``'s own
            validation.

    Example:
        >>> from datetime import datetime, timezone
        >>> from korchestrator.models.state import AgentState
        >>> from korchestrator.serializers import from_json, to_json
        >>> state = AgentState(
        ...     run_id="r1", objective="summarize the quarterly report",
        ...     transaction_time=datetime(2026, 7, 23, tzinfo=timezone.utc),
        ... )
        >>> from_json(to_json(state), AgentState) == state
        True
    """
    if model_cls not in _CURRENT_SCHEMA_VERSION:
        raise ValidationError(
            f"{model_cls.__name__} is not a serializable model. Supported: "
            f"{_supported_names()}. (AgentGraph is deliberately excluded — ADR 0017.)",
            code="KORCH_VALIDATION_FAILED",
        )
    try:
        envelope = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"Malformed JSON payload: {exc}.", code="KORCH_VALIDATION_FAILED"
        ) from exc

    if not isinstance(envelope, dict) or "schema_version" not in envelope or "data" not in envelope:
        raise ValidationError(
            "Payload is not a korchestrator serialization envelope — expected "
            "{'schema_version', 'korchestrator_version', 'type', 'data'}.",
            code="KORCH_VALIDATION_FAILED",
        )
    if envelope.get("type") != model_cls.__name__:
        raise ValidationError(
            f"Payload is a serialised {envelope.get('type')!r}, not {model_cls.__name__!r}.",
            code="KORCH_VALIDATION_FAILED",
        )

    payload_version = envelope["schema_version"]
    current_version = _CURRENT_SCHEMA_VERSION[model_cls]
    if payload_version > current_version:
        raise ValidationError(
            f"Payload schema_version {payload_version} for {model_cls.__name__} is newer than "
            f"the installed package supports ({current_version}). Upgrade korchestrator.",
            code="KORCH_VALIDATION_FAILED",
        )

    data = envelope["data"]
    version = payload_version
    while version < current_version:
        migrate = _MIGRATIONS.get((model_cls, version))
        if migrate is None:
            raise ValidationError(
                f"No migration registered for {model_cls.__name__} from schema_version "
                f"{version} to {version + 1}.",
                code="KORCH_VALIDATION_FAILED",
            )
        data = migrate(data)
        version += 1

    try:
        return model_cls.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(
            f"Payload does not match {model_cls.__name__}: {exc}.",
            code="KORCH_VALIDATION_FAILED",
        ) from exc
