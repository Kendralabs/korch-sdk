"""Integration: a built-in routing strategy drives model selection through a full swarm run.

Each strategy's ranking/selection logic is unit-tested in isolation under ``tests/unit/routing/``,
and ``tests/unit/services/test_run.py::test_custom_router_influences_the_run`` already proves a
user-authored :class:`~korchestrator.interfaces.BaseRouter` reaches the gateway. This file's job
is the other half named by spec 12 P10.2 ("routing strategies"): proving a **built-in** strategy —
not just the user-function escape hatch — is actually consulted per agent and its choice reaches
the model gateway, end to end through ``Swarm.run()``.
"""

from __future__ import annotations

import pytest

from korchestrator import Agent, Swarm
from korchestrator.models.state import RunStatus
from korchestrator.providers import MockLM
from korchestrator.routing.algorithmic import AlgorithmicRouter


def test_the_algorithmic_router_picks_the_cheapest_eligible_model_end_to_end() -> None:
    pytest.importorskip("dspy")
    # Weighting entirely on cost must route to the cheapest of the built-in model cards
    # (gpt-4o-mini, per routing/model_cards.py's catalogue) without any explicit `model=`.
    gateway = MockLM()
    swarm = Swarm(
        objective="Summarize the incident report clearly",
        model_gateway=gateway,
        router=AlgorithmicRouter({"cost": 1.0}),
    ).add(Agent(id="analyst", role="analyst"))

    result = swarm.run()

    assert result.status is RunStatus.COMPLETED
    assert {call.model for call in gateway.calls} == {"gpt-4o-mini"}


def test_the_algorithmic_router_picks_the_highest_quality_model_end_to_end() -> None:
    pytest.importorskip("dspy")
    # The same run, weighted entirely on quality instead, must route to a different model —
    # proving the strategy's choice (not just *a* choice) reaches the gateway.
    gateway = MockLM()
    swarm = Swarm(
        objective="Summarize the incident report clearly",
        model_gateway=gateway,
        router=AlgorithmicRouter({"quality": 1.0}),
    ).add(Agent(id="analyst", role="analyst"))

    result = swarm.run()

    assert result.status is RunStatus.COMPLETED
    assert {call.model for call in gateway.calls} == {"gpt-4o"}
