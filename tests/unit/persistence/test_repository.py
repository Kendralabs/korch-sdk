"""Unit tests for the in-memory GraphRepository (spec 05 §1, P7.5/P7.6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from korchestrator.interfaces import GraphRepository
from korchestrator.models.context_graph import EventNode
from korchestrator.models.state import AgentState
from korchestrator.persistence import InMemoryGraphRepository

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=1)
EARLIER = NOW - timedelta(hours=1)


def _state(run_id: str = "r1") -> AgentState:
    return AgentState(
        run_id=run_id, objective="summarize the quarterly report", transaction_time=NOW
    )


def _node(
    node_id: str = "n1",
    *,
    run_id: str | None = "r1",
    valid_time: datetime = NOW,
    transaction_time: datetime = NOW,
) -> EventNode:
    return EventNode(
        id=node_id,
        tenant_id="acme",
        run_id=run_id,
        content="the worker escalated",
        provenance="worker",
        event_type="message",
        valid_time=valid_time,
        transaction_time=transaction_time,
    )


def test_the_repository_satisfies_the_protocol() -> None:
    assert isinstance(InMemoryGraphRepository(), GraphRepository)


async def test_load_state_returns_none_when_nothing_was_saved() -> None:
    repo = InMemoryGraphRepository()
    assert await repo.load_state("r1", tenant_id="acme") is None


async def test_save_then_load_round_trips() -> None:
    repo = InMemoryGraphRepository()
    state = _state()
    await repo.save_state(state, tenant_id="acme")
    assert await repo.load_state("r1", tenant_id="acme") == state


async def test_save_state_replaces_the_prior_save_for_the_same_run() -> None:
    repo = InMemoryGraphRepository()
    await repo.save_state(_state(), tenant_id="acme")
    updated = _state().model_copy(update={"superstep": 3})
    await repo.save_state(updated, tenant_id="acme")
    assert await repo.load_state("r1", tenant_id="acme") == updated


async def test_tenants_are_isolated() -> None:
    repo = InMemoryGraphRepository()
    await repo.save_state(_state(), tenant_id="acme")
    assert await repo.load_state("r1", tenant_id="other-tenant") is None


async def test_different_runs_coexist_within_a_tenant() -> None:
    repo = InMemoryGraphRepository()
    await repo.save_state(_state("r1"), tenant_id="acme")
    await repo.save_state(_state("r2"), tenant_id="acme")
    assert (await repo.load_state("r1", tenant_id="acme")).run_id == "r1"  # type: ignore[union-attr]
    assert (await repo.load_state("r2", tenant_id="acme")).run_id == "r2"  # type: ignore[union-attr]


# --- Context Graph nodes (P7.6) -------------------------------------------------------------------


async def test_query_nodes_is_empty_before_anything_is_recorded() -> None:
    repo = InMemoryGraphRepository()
    assert await repo.query_nodes(tenant_id="acme") == ()


async def test_record_then_query_round_trips() -> None:
    repo = InMemoryGraphRepository()
    node = _node()
    await repo.record_node(node, tenant_id="acme")
    assert await repo.query_nodes(tenant_id="acme") == (node,)


async def test_recording_never_overwrites_a_prior_node() -> None:
    repo = InMemoryGraphRepository()
    first = _node("n1")
    second = _node("n2")
    await repo.record_node(first, tenant_id="acme")
    await repo.record_node(second, tenant_id="acme")
    assert await repo.query_nodes(tenant_id="acme") == (first, second)


async def test_query_nodes_is_tenant_scoped() -> None:
    repo = InMemoryGraphRepository()
    await repo.record_node(_node(), tenant_id="acme")
    assert await repo.query_nodes(tenant_id="other-tenant") == ()


async def test_query_nodes_filters_by_run_id() -> None:
    repo = InMemoryGraphRepository()
    in_run = _node("n1", run_id="r1")
    other_run = _node("n2", run_id="r2")
    await repo.record_node(in_run, tenant_id="acme")
    await repo.record_node(other_run, tenant_id="acme")
    assert await repo.query_nodes(tenant_id="acme", run_id="r1") == (in_run,)


async def test_query_nodes_time_travels_on_transaction_time() -> None:
    repo = InMemoryGraphRepository()
    early = _node("n1", transaction_time=EARLIER)
    late = _node("n2", transaction_time=LATER)
    await repo.record_node(early, tenant_id="acme")
    await repo.record_node(late, tenant_id="acme")
    assert await repo.query_nodes(tenant_id="acme", as_of=NOW) == (early,)
    assert await repo.query_nodes(tenant_id="acme", as_of=LATER) == (early, late)


async def test_query_nodes_time_travels_on_valid_time() -> None:
    repo = InMemoryGraphRepository()
    early = _node("n1", valid_time=EARLIER)
    late = _node("n2", valid_time=LATER)
    await repo.record_node(early, tenant_id="acme")
    await repo.record_node(late, tenant_id="acme")
    assert await repo.query_nodes(tenant_id="acme", valid_at=NOW) == (early,)
