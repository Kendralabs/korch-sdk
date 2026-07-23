"""Unit tests for ContextGraphClient (spec 05 §5, P7.6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from korchestrator.models.context_graph import DecisionNode, EventNode
from korchestrator.persistence import ContextGraphClient, InMemoryGraphRepository

NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=1)


def _client() -> ContextGraphClient:
    return ContextGraphClient(InMemoryGraphRepository())


async def test_record_decision_returns_a_decision_node() -> None:
    client = _client()
    node = await client.record_decision(
        tenant_id="acme",
        content="Escalate to a human reviewer",
        provenance="lead",
        valid_time=NOW,
        transaction_time=NOW,
    )
    assert isinstance(node, DecisionNode)
    assert node.kind == "decision"
    assert node.content == "Escalate to a human reviewer"
    assert node.provenance == "lead"
    assert node.confidence == 1.0
    assert node.tenant_id == "acme"


async def test_record_event_returns_an_event_node() -> None:
    client = _client()
    node = await client.record_event(
        tenant_id="acme",
        content="Called the search tool",
        provenance="worker",
        event_type="tool_call",
        valid_time=NOW,
        transaction_time=NOW,
    )
    assert isinstance(node, EventNode)
    assert node.kind == "event"
    assert node.event_type == "tool_call"


async def test_recorded_nodes_are_queryable() -> None:
    client = _client()
    decision = await client.record_decision(
        tenant_id="acme",
        content="Approve the plan",
        provenance="lead",
        valid_time=NOW,
        transaction_time=NOW,
    )
    event = await client.record_event(
        tenant_id="acme",
        content="Plan approved",
        provenance="lead",
        event_type="message",
        valid_time=NOW,
        transaction_time=NOW,
    )
    assert await client.query(tenant_id="acme") == (decision, event)


async def test_query_is_tenant_scoped() -> None:
    client = _client()
    await client.record_decision(
        tenant_id="acme",
        content="Approve the plan",
        provenance="lead",
        valid_time=NOW,
        transaction_time=NOW,
    )
    assert await client.query(tenant_id="other-tenant") == ()


async def test_query_supports_time_travel() -> None:
    client = _client()
    await client.record_decision(
        tenant_id="acme",
        content="Initial decision",
        provenance="lead",
        valid_time=NOW,
        transaction_time=NOW,
    )
    later_decision = await client.record_decision(
        tenant_id="acme",
        content="Revised decision",
        provenance="lead",
        valid_time=LATER,
        transaction_time=LATER,
    )
    as_of_now = await client.query(tenant_id="acme", as_of=NOW)
    assert later_decision not in as_of_now
    assert len(as_of_now) == 1


async def test_content_is_redacted_before_it_reaches_the_repository() -> None:
    repo = InMemoryGraphRepository()
    client = ContextGraphClient(repo)
    await client.record_event(
        tenant_id="acme",
        content="Contact jane.doe@example.com for approval",
        provenance="lead",
        event_type="message",
        valid_time=NOW,
        transaction_time=NOW,
    )
    [node] = await repo.query_nodes(tenant_id="acme")
    assert "jane.doe@example.com" not in node.content
    assert "[MASKED_EMAIL]" in node.content


async def test_a_correction_is_a_new_node_not_a_mutation() -> None:
    # Event sourcing: recording twice with the same content produces two immutable nodes with
    # distinct ids, never an overwrite of the first.
    client = _client()
    first = await client.record_decision(
        tenant_id="acme",
        content="Approve the plan",
        provenance="lead",
        valid_time=NOW,
        transaction_time=NOW,
    )
    second = await client.record_decision(
        tenant_id="acme",
        content="Approve the plan",
        provenance="lead",
        valid_time=LATER,
        transaction_time=LATER,
    )
    assert first.id != second.id
    nodes = await client.query(tenant_id="acme")
    assert nodes == (first, second)
