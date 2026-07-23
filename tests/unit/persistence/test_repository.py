"""Unit tests for the in-memory GraphRepository (spec 05 §1, P7.5)."""

from __future__ import annotations

from datetime import datetime, timezone

from korchestrator.interfaces import GraphRepository
from korchestrator.models.state import AgentState
from korchestrator.persistence import InMemoryGraphRepository

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _state(run_id: str = "r1") -> AgentState:
    return AgentState(
        run_id=run_id, objective="summarize the quarterly report", transaction_time=NOW
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
