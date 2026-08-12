"""KorchestratorClient run-lifecycle tests (spec 04 §7.3/§7.4, P9.3)."""

from __future__ import annotations

from unittest import mock

import pytest

httpx = pytest.importorskip("httpx")
respx = pytest.importorskip("respx")

from korchestrator.clients import KorchestratorClient  # noqa: E402 — after importorskip guards
from korchestrator.exceptions import ApiError  # noqa: E402
from korchestrator.models import AgentConfig, AgentPersona, RunStatus  # noqa: E402

BASE_URL = "https://engine.example.com"
STARTED_AT = "2026-07-23T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _no_real_sleep() -> mock.AsyncMock:
    with mock.patch("korchestrator.clients.client.asyncio.sleep", new_callable=mock.AsyncMock) as m:
        yield m


def _run_body(*, status: object = "running", **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "run_id": "r1",
        "status": status,
        "final_answer": "",
        "supersteps": 0,
        "trust_score": 1.0,
        "message_count": 0,
        "started_at": STARTED_AT,
    }
    body.update(overrides)
    return body


# --- run / run_swarm --------------------------------------------------------------------------


@respx.mock
def test_run_posts_the_objective_and_returns_the_initial_result() -> None:
    route = respx.post(f"{BASE_URL}/v1/run/auto").mock(
        return_value=httpx.Response(200, json=_run_body())
    )
    client = KorchestratorClient(BASE_URL, api_key="sk-example")
    result = client.run("Summarize the quarterly incident reports")
    assert result.run_id == "r1"
    assert result.status is RunStatus.RUNNING
    body = route.calls.last.request.content
    assert b"Summarize the quarterly incident reports" in body
    client.close()


@respx.mock
def test_run_omits_tenant_id_when_not_given() -> None:
    route = respx.post(f"{BASE_URL}/v1/run/auto").mock(
        return_value=httpx.Response(200, json=_run_body())
    )
    client = KorchestratorClient(BASE_URL)
    client.run("Summarize the quarterly incident reports")
    assert b"tenant_id" not in route.calls.last.request.content
    client.close()


@respx.mock
def test_run_includes_tenant_id_when_given() -> None:
    route = respx.post(f"{BASE_URL}/v1/run/auto").mock(
        return_value=httpx.Response(200, json=_run_body())
    )
    client = KorchestratorClient(BASE_URL)
    client.run("Summarize the quarterly incident reports", tenant_id="acme")
    assert b'"tenant_id":"acme"' in route.calls.last.request.content
    client.close()


@respx.mock
def test_run_swarm_serializes_agents_and_edges() -> None:
    route = respx.post(f"{BASE_URL}/v1/run/swarm").mock(
        return_value=httpx.Response(200, json=_run_body())
    )
    client = KorchestratorClient(BASE_URL)
    agent = AgentConfig(id="lead", persona=AgentPersona(role="review-lead"))
    result = client.run_swarm([agent], [("a", "lead")], objective="Review this change for security")
    assert result.run_id == "r1"
    import json

    sent = json.loads(route.calls.last.request.content)
    assert sent["agents"][0]["id"] == "lead"
    assert sent["edges"] == [["a", "lead"]]
    client.close()


@respx.mock
def test_run_swarm_includes_tenant_id_when_given() -> None:
    route = respx.post(f"{BASE_URL}/v1/run/swarm").mock(
        return_value=httpx.Response(200, json=_run_body())
    )
    client = KorchestratorClient(BASE_URL)
    agent = AgentConfig(id="lead", persona=AgentPersona(role="review-lead"))
    client.run_swarm([agent], objective="Review this change for security", tenant_id="acme")
    assert b'"tenant_id":"acme"' in route.calls.last.request.content
    client.close()


# --- get_run / status normalization ----------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, RunStatus.STARTED),
        (1, RunStatus.RUNNING),
        (2, RunStatus.COMPLETED),
        (3, RunStatus.FAILED),
        (4, RunStatus.CANCELLED),
        (5, RunStatus.GOVERNANCE_PAUSED),
        (6, RunStatus.TIMED_OUT),
    ],
)
@respx.mock
def test_get_run_normalizes_every_documented_numeric_status(code: int, expected: RunStatus) -> None:
    respx.get(f"{BASE_URL}/v1/run/r1").mock(
        return_value=httpx.Response(200, json=_run_body(status=code))
    )
    client = KorchestratorClient(BASE_URL)
    result = client.get_run("r1")
    assert result.status is expected
    client.close()


@respx.mock
def test_get_run_accepts_an_already_string_status() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1").mock(
        return_value=httpx.Response(200, json=_run_body(status="completed"))
    )
    client = KorchestratorClient(BASE_URL)
    assert client.get_run("r1").status is RunStatus.COMPLETED
    client.close()


@respx.mock
def test_get_run_rejects_an_unrecognised_numeric_status() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1").mock(
        return_value=httpx.Response(200, json=_run_body(status=99))
    )
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.get_run("r1")
    client.close()


@respx.mock
def test_get_run_wraps_a_malformed_body_as_api_error() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.get_run("r1")
    client.close()


@respx.mock
def test_get_run_wraps_a_non_json_body_as_api_error() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1").mock(return_value=httpx.Response(200, text="not json"))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.get_run("r1")
    client.close()


@respx.mock
def test_get_run_wraps_a_non_object_body_as_api_error() -> None:
    respx.get(f"{BASE_URL}/v1/run/r1").mock(
        return_value=httpx.Response(200, json=["not", "a", "dict"])
    )
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.get_run("r1")
    client.close()


# --- wait / run_and_wait -----------------------------------------------------------------------


@respx.mock
def test_wait_polls_until_a_terminal_status(_no_real_sleep: mock.AsyncMock) -> None:
    route = respx.get(f"{BASE_URL}/v1/run/r1").mock(
        side_effect=[
            httpx.Response(200, json=_run_body(status="running")),
            httpx.Response(200, json=_run_body(status="running")),
            httpx.Response(200, json=_run_body(status="completed")),
        ]
    )
    client = KorchestratorClient(BASE_URL)
    result = client.wait("r1")
    assert result.status is RunStatus.COMPLETED
    assert route.call_count == 3
    assert _no_real_sleep.await_count == 2
    client.close()


@respx.mock
def test_wait_keeps_polling_through_governance_paused(_no_real_sleep: mock.AsyncMock) -> None:
    # governance_paused is not terminal — an operator must act (P9.4); wait() must not return early.
    route = respx.get(f"{BASE_URL}/v1/run/r1").mock(
        side_effect=[
            httpx.Response(200, json=_run_body(status="governance_paused")),
            httpx.Response(200, json=_run_body(status="failed")),
        ]
    )
    client = KorchestratorClient(BASE_URL)
    result = client.wait("r1")
    assert result.status is RunStatus.FAILED
    assert route.call_count == 2
    client.close()


@respx.mock
def test_run_and_wait_starts_then_waits(_no_real_sleep: mock.AsyncMock) -> None:
    respx.post(f"{BASE_URL}/v1/run/auto").mock(
        return_value=httpx.Response(200, json=_run_body(run_id="r2", status="started"))
    )
    respx.get(f"{BASE_URL}/v1/run/r2").mock(
        return_value=httpx.Response(200, json=_run_body(run_id="r2", status="completed"))
    )
    client = KorchestratorClient(BASE_URL)
    result = client.run_and_wait("Summarize the quarterly incident reports")
    assert result.run_id == "r2"
    assert result.status is RunStatus.COMPLETED
    client.close()


# --- list_runs / get_run_summary -----------------------------------------------------------------


@respx.mock
def test_list_runs_parses_a_bare_array() -> None:
    respx.get(f"{BASE_URL}/v1/runs").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"run_id": "r1", "status": "completed", "superstep": 3},
                {"run_id": "r2", "status": 1, "superstep": 1},
            ],
        )
    )
    client = KorchestratorClient(BASE_URL)
    runs = client.list_runs()
    assert [r.run_id for r in runs] == ["r1", "r2"]
    assert runs[1].status is RunStatus.RUNNING
    client.close()


@respx.mock
def test_list_runs_parses_a_wrapped_object() -> None:
    respx.get(f"{BASE_URL}/v1/runs").mock(
        return_value=httpx.Response(
            200, json={"runs": [{"run_id": "r1", "status": "completed", "superstep": 3}]}
        )
    )
    client = KorchestratorClient(BASE_URL)
    runs = client.list_runs()
    assert len(runs) == 1
    client.close()


@respx.mock
def test_list_runs_passes_tenant_id_as_a_query_param() -> None:
    route = respx.get(f"{BASE_URL}/v1/runs").mock(return_value=httpx.Response(200, json=[]))
    client = KorchestratorClient(BASE_URL)
    client.list_runs(tenant_id="acme")
    assert route.calls.last.request.url.params["tenant_id"] == "acme"
    client.close()


@respx.mock
def test_list_runs_rejects_an_unexpected_response_shape() -> None:
    respx.get(f"{BASE_URL}/v1/runs").mock(return_value=httpx.Response(200, json={"oops": True}))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.list_runs()
    client.close()


@respx.mock
def test_list_runs_rejects_a_non_object_item() -> None:
    respx.get(f"{BASE_URL}/v1/runs").mock(return_value=httpx.Response(200, json=["not-a-dict"]))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.list_runs()
    client.close()


@respx.mock
def test_get_run_summary_rejects_a_body_missing_required_fields() -> None:
    respx.get(f"{BASE_URL}/v1/runs/r1/summary").mock(
        return_value=httpx.Response(200, json={"status": "completed"})
    )
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.get_run_summary("r1")
    client.close()


@respx.mock
def test_get_run_summary_parses_the_summary_shape() -> None:
    respx.get(f"{BASE_URL}/v1/runs/r1/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "run_id": "r1",
                "status": "completed",
                "superstep": 4,
                "final_answer": "done",
                "message_count": 6,
            },
        )
    )
    client = KorchestratorClient(BASE_URL)
    summary = client.get_run_summary("r1")
    assert summary.run_id == "r1"
    assert summary.status is RunStatus.COMPLETED
    assert summary.message_count == 6
    client.close()
