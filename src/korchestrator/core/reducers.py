"""Kernel layer (L1), framework-free. Imports: korchestrator.exceptions, types, stdlib, pydantic.

The four channel reducers that merge each superstep's deltas into the next ``AgentState``. Shared
state mutates only through these; there is no fifth reducer without an ADR (spec 06 §3).

A reducer is applied **once per channel per superstep**, to the channel's current value and the
complete set of that superstep's writes as ``(agent_id, value)`` pairs. Each reducer sorts its
deltas by ``agent_id`` internally, so it is a pure, order-independent function of ``(current, set
of deltas)`` — ``asyncio.gather`` completion order and Temporal's replay interleaving can never
change the result. The ``agent_id`` key is added to the spec 06 §3 ``Sequence[T]`` signature
precisely because the order-independence the spec mandates for ``LastValue``/``Append`` needs a
total order over the deltas, and ``agent_id`` (unique per node) is that order.

The reducer laws (associativity/order-independence/totality, and idempotence where claimed) are
proved by property-based tests in ``tests/unit/core/test_reducers.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from korchestrator.exceptions import ValidationError
from korchestrator.types import JSONValue

__all__ = ["Append", "Delta", "LastValue", "MergeDict", "Reducer", "UniqueAppend"]

# One agent's write to a channel: its agent_id (the total-order key) and the value it wrote.
Delta = tuple[str, JSONValue]


@runtime_checkable
class Reducer(Protocol):
    """Merge a channel's prior value with one superstep's deltas.

    Implementations MUST be associative and order-independent: the result depends only on the
    current value and the *set* of ``(agent_id, value)`` deltas, never on their order.
    """

    def __call__(self, current: JSONValue, deltas: Sequence[Delta]) -> JSONValue:
        """Return the merged channel value."""
        ...


def _in_agent_order(deltas: Sequence[Delta]) -> list[JSONValue]:
    """Return the delta values in ascending ``agent_id`` order (the canonical order)."""
    return [value for _, value in sorted(deltas, key=lambda delta: delta[0])]


def _as_list(value: JSONValue) -> list[JSONValue]:
    """Coerce a channel's current value to a list (``None`` means the empty channel)."""
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _as_dict(value: JSONValue) -> dict[str, JSONValue]:
    """Coerce a value to a dict for merging; a non-dict on a MergeDict channel is invalid."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    raise ValidationError(
        f"MergeDict channels require mapping values, got {type(value).__name__}. "
        "Bind this channel to a different reducer or emit a dict.",
        code="KORCH_VALIDATION_FAILED",
    )


def _deep_merge(base: dict[str, JSONValue], incoming: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Deep-merge ``incoming`` into ``base``; conflicting leaves take ``incoming`` (LastValue)."""
    result = dict(base)
    for key, value in incoming.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = value
    return result


class LastValue:
    """Keep the value written by the highest ``agent_id`` this superstep, else the current value.

    Within one superstep every delta shares the same ``superstep``, so the ``(superstep,
    agent_id)`` total order reduces to ``agent_id``; the current value carries the prior
    superstep's winner. Associative, order-independent, and idempotent.

    Example:
        >>> from korchestrator.core import LastValue
        >>> LastValue()("old", [("a", 1), ("b", 2)])
        2
    """

    def __call__(self, current: JSONValue, deltas: Sequence[Delta]) -> JSONValue:
        """Return the highest-``agent_id`` delta value, or ``current`` if there are no deltas."""
        if not deltas:
            return current
        return max(deltas, key=lambda delta: delta[0])[1]


class Append:
    """Concatenate deltas onto a list channel in ``agent_id`` order.

    Associative and order-independent (the deltas are sorted by ``agent_id``, never by arrival),
    but **deliberately not idempotent** — re-applying a delta appends it again.

    Example:
        >>> from korchestrator.core import Append
        >>> Append()([0], [("b", 2), ("a", 1)])
        [0, 1, 2]
    """

    def __call__(self, current: JSONValue, deltas: Sequence[Delta]) -> JSONValue:
        """Return ``current`` (as a list) followed by the deltas in ``agent_id`` order."""
        return [*_as_list(current), *_in_agent_order(deltas)]


class UniqueAppend:
    """Append only values not already present, preserving first-seen position.

    Associative, order-independent, and idempotent (at-least-once delivery cannot duplicate).

    Example:
        >>> from korchestrator.core import UniqueAppend
        >>> UniqueAppend()([1], [("b", 2), ("a", 1)])
        [1, 2]
    """

    def __call__(self, current: JSONValue, deltas: Sequence[Delta]) -> JSONValue:
        """Return ``current`` extended with each new delta value, skipping duplicates."""
        result = _as_list(current)
        for value in _in_agent_order(deltas):
            if value not in result:
                result.append(value)
        return result


class MergeDict:
    """Deep-merge mapping channels; conflicting leaves resolve by ``LastValue`` (highest agent_id).

    Associative, order-independent, and idempotent.

    Example:
        >>> from korchestrator.core import MergeDict
        >>> MergeDict()({"a": 1}, [("x", {"b": 2})]) == {"a": 1, "b": 2}
        True
    """

    def __call__(self, current: JSONValue, deltas: Sequence[Delta]) -> JSONValue:
        """Return the deep merge of ``current`` with every delta, in ``agent_id`` order."""
        result = _as_dict(current)
        for value in _in_agent_order(deltas):
            result = _deep_merge(result, _as_dict(value))
        return result
