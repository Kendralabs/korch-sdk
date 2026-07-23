"""KorchestratorClient discovery tests (spec 04 §7.3, P9.6)."""

from __future__ import annotations

import httpx
import pytest
import respx

from korchestrator.clients import KorchestratorClient
from korchestrator.exceptions import ApiError

BASE_URL = "https://engine.example.com"


# --- tools ------------------------------------------------------------------------------------


@respx.mock
def test_tools_parses_a_wrapped_object() -> None:
    respx.get(f"{BASE_URL}/v1/tools").mock(
        return_value=httpx.Response(
            200,
            json={
                "tools": [
                    {
                        "name": "grep",
                        "description": "Search files",
                        "input_schema": {"type": "object"},
                    }
                ]
            },
        )
    )
    client = KorchestratorClient(BASE_URL)
    (tool,) = client.tools()
    assert tool.name == "grep"
    assert tool.input_schema == {"type": "object"}
    client.close()


@respx.mock
def test_tools_parses_a_bare_array() -> None:
    respx.get(f"{BASE_URL}/v1/tools").mock(
        return_value=httpx.Response(200, json=[{"name": "search"}])
    )
    client = KorchestratorClient(BASE_URL)
    (tool,) = client.tools()
    assert tool.name == "search"
    assert tool.description == ""
    assert tool.input_schema == {}
    client.close()


@respx.mock
def test_tools_rejects_an_unexpected_shape() -> None:
    respx.get(f"{BASE_URL}/v1/tools").mock(return_value=httpx.Response(200, json={"oops": True}))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.tools()
    client.close()


# --- models -----------------------------------------------------------------------------------


@respx.mock
def test_models_parses_the_model_card_shape() -> None:
    respx.get(f"{BASE_URL}/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "gpt-4o-mini",
                        "provider": "openai",
                        "description": "fast, cheap",
                        "context_window": 128000,
                        "cost_per_1k_input_usd": 0.00015,
                        "cost_per_1k_output_usd": 0.0006,
                        "latency_p50_ms": 500,
                        "quality_score": 0.8,
                    }
                ]
            },
        )
    )
    client = KorchestratorClient(BASE_URL)
    (model,) = client.models()
    assert model.name == "gpt-4o-mini"
    assert model.quality_score == 0.8
    client.close()


@respx.mock
def test_models_rejects_an_unexpected_shape() -> None:
    respx.get(f"{BASE_URL}/v1/models").mock(return_value=httpx.Response(200, json={"oops": True}))
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.models()
    client.close()


# --- swarm_templates ----------------------------------------------------------------------------


@respx.mock
def test_swarm_templates_parses_agents_and_edges() -> None:
    respx.get(f"{BASE_URL}/v1/swarm-templates").mock(
        return_value=httpx.Response(
            200,
            json={
                "templates": [
                    {
                        "name": "code-review",
                        "description": "Security + perf review",
                        "agents": [
                            {"id": "lead", "persona": {"role": "review-lead"}},
                        ],
                        "edges": [],
                    }
                ]
            },
        )
    )
    client = KorchestratorClient(BASE_URL)
    (template,) = client.swarm_templates()
    assert template.name == "code-review"
    assert template.agents[0].id == "lead"
    client.close()


@respx.mock
def test_swarm_templates_rejects_an_unexpected_shape() -> None:
    respx.get(f"{BASE_URL}/v1/swarm-templates").mock(
        return_value=httpx.Response(200, json={"oops": True})
    )
    client = KorchestratorClient(BASE_URL)
    with pytest.raises(ApiError):
        client.swarm_templates()
    client.close()
