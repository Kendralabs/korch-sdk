"""Property-based proofs of the reducer algebraic laws (spec 06 §3, P2.2).

Every reducer MUST be associative and order-independent so that ``asyncio.gather`` completion
order and Temporal's replay interleaving cannot change the merged result. ``UniqueAppend``,
``MergeDict`` and ``LastValue`` are additionally idempotent (at-least-once delivery is real);
``Append`` is deliberately NOT — a test locks that so nobody "fixes" it.
"""

from __future__ import annotations

import string
from collections.abc import Sequence

import pytest

pytest.importorskip("hypothesis")

from hypothesis import given
from hypothesis import strategies as st

from korchestrator.core.reducers import (
    Append,
    Delta,
    LastValue,
    MergeDict,
    UniqueAppend,
)

_AGENT_IDS = st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=6)
_SCALARS = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-1000, max_value=1000)
    | st.floats(allow_nan=False, allow_infinity=False, width=32)
    | st.text(max_size=8)
)
# Distinct agent_ids per superstep (a channel gets at most one write per agent).
_scalar_deltas = st.dictionaries(_AGENT_IDS, _SCALARS, max_size=6).map(lambda d: list(d.items()))
_dict_values = st.dictionaries(st.text(max_size=4), _SCALARS, max_size=4)
_dict_deltas = st.dictionaries(_AGENT_IDS, _dict_values, max_size=6).map(lambda d: list(d.items()))


# --- order-independence: the load-bearing law ---------------------------------------------------


@given(deltas=_scalar_deltas)
def test_last_value_is_order_independent(deltas: list[Delta]) -> None:
    _assert_order_independent(LastValue(), None, deltas)


@given(deltas=_scalar_deltas)
def test_append_is_order_independent(deltas: list[Delta]) -> None:
    _assert_order_independent(Append(), [], deltas)


@given(deltas=_scalar_deltas)
def test_unique_append_is_order_independent(deltas: list[Delta]) -> None:
    _assert_order_independent(UniqueAppend(), [], deltas)


@given(deltas=_dict_deltas)
def test_merge_dict_is_order_independent(deltas: list[Delta]) -> None:
    _assert_order_independent(MergeDict(), {}, deltas)


def _assert_order_independent(reducer: object, current: object, deltas: list[Delta]) -> None:
    call = reducer  # a callable (current, deltas) -> value
    reference = call(current, deltas)  # type: ignore[operator]
    for permutation in _permutations(deltas):
        assert call(current, permutation) == reference  # type: ignore[operator]


def _permutations(items: list[Delta]) -> list[list[Delta]]:
    # A few deterministic rotations/reversal — enough to catch order sensitivity cheaply.
    if len(items) < 2:
        return [items]
    return [items, items[::-1], items[1:] + items[:1], items[-1:] + items[:-1]]


# --- totality -----------------------------------------------------------------------------------


@given(current=_SCALARS)
def test_last_value_empty_deltas_keeps_current(current: object) -> None:
    assert LastValue()(current, []) == current


def test_empty_deltas_are_defined_for_every_reducer() -> None:
    assert Append()([1, 2], []) == [1, 2]
    assert UniqueAppend()([1, 2], []) == [1, 2]
    assert MergeDict()({"a": 1}, []) == {"a": 1}
    assert LastValue()("x", []) == "x"


# --- idempotence under re-application (at-least-once delivery) -----------------------------------


@given(deltas=_scalar_deltas)
def test_last_value_is_idempotent(deltas: list[Delta]) -> None:
    reducer = LastValue()
    once = reducer(None, deltas)
    assert reducer(once, deltas) == once


@given(deltas=_scalar_deltas)
def test_unique_append_is_idempotent(deltas: list[Delta]) -> None:
    reducer = UniqueAppend()
    once = reducer([], deltas)
    assert reducer(once, deltas) == once


@given(deltas=_dict_deltas)
def test_merge_dict_is_idempotent(deltas: list[Delta]) -> None:
    reducer = MergeDict()
    once = reducer({}, deltas)
    assert reducer(once, deltas) == once


def test_append_is_deliberately_not_idempotent() -> None:
    reducer = Append()
    once = reducer([], [("a", 1)])
    assert reducer(once, [("a", 1)]) == [1, 1] != once


# --- concrete behaviour locks -------------------------------------------------------------------


def test_last_value_takes_the_highest_agent_id() -> None:
    assert LastValue()("old", [("a", 1), ("c", 3), ("b", 2)]) == 3


def test_append_concatenates_in_agent_id_order() -> None:
    assert Append()([0], [("c", 3), ("a", 1), ("b", 2)]) == [0, 1, 2, 3]


def test_append_coerces_a_bare_scalar_current_value_to_a_single_element_list() -> None:
    # Defensive: a channel's current value should always already be a list, but _as_list must
    # still be total (reducer law) over a malformed/externally-set scalar.
    assert Append()(0, [("a", 1)]) == [0, 1]


def test_append_on_a_channel_with_no_prior_writes_starts_from_an_empty_list() -> None:
    # Every list channel's very first write sees current=None (spec 06 §3) — the most common
    # real path through _as_list's None branch, not just a defensive edge case.
    assert Append()(None, [("a", 1)]) == [1]


def test_merge_dict_coerces_a_none_current_value_to_an_empty_mapping() -> None:
    assert MergeDict()(None, [("a", {"x": 1})]) == {"x": 1}


def test_unique_append_preserves_first_seen_and_skips_duplicates() -> None:
    assert UniqueAppend()([1], [("b", 2), ("a", 1), ("c", 2)]) == [1, 2]


def test_merge_dict_deep_merges_and_resolves_conflicts_by_highest_agent_id() -> None:
    result = MergeDict()(
        {"outer": {"keep": 1}},
        [("a", {"outer": {"x": 2}}), ("b", {"outer": {"keep": 9}})],
    )
    assert result == {"outer": {"keep": 9, "x": 2}}


def test_merge_dict_rejects_a_non_mapping_delta() -> None:
    from korchestrator.exceptions import ValidationError

    reducer = MergeDict()
    deltas: Sequence[Delta] = [("a", [1, 2])]
    try:
        reducer({}, deltas)
    except ValidationError as exc:
        assert exc.code == "KORCH_VALIDATION_FAILED"
    else:
        raise AssertionError("expected ValidationError for a non-mapping MergeDict delta")
