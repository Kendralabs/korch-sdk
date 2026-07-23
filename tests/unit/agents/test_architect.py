"""Unit tests for the ArchitectAgent (spec 05 §36, P4.7)."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from korchestrator.agents import ArchitectAgent
from korchestrator.agents.architect import _agents_from_roles, _slug
from korchestrator.exceptions import ConfigurationError, MissingExtraError, ValidationError
from korchestrator.models.plan import ExecutionPlan
from korchestrator.providers import MockLM

OBJECTIVE = "Summarize the quarterly incident reports"
_STRUCTURED = (
    "[[ ## roles ## ]]\nresearcher\nwriter\n\n"
    "[[ ## rationale ## ]]\nsplit the work\n\n[[ ## completed ## ]]"
)


# --- pure parsing (no dspy) ---------------------------------------------------------------------


def test_slug_normalises_or_rejects() -> None:
    assert _slug("Security Reviewer") == "security-reviewer"
    assert _slug("  !!!  ") == ""


def test_roles_are_parsed_deduped_and_bounded() -> None:
    roles = "- Researcher\n- researcher\n* Writer\n\n" + "\n".join(f"role {i}" for i in range(20))
    configs = _agents_from_roles(roles)
    ids = [c.id for c in configs]
    assert ids[:2] == ["researcher", "writer"]  # deduped (case-insensitive slug), order preserved
    assert len(configs) <= 8  # bounded


def test_empty_roles_yield_no_agents() -> None:
    assert _agents_from_roles("   \n\n!!!") == ()


# --- plan() guards (no dspy) --------------------------------------------------------------------


async def test_short_objective_is_rejected() -> None:
    with pytest.raises(ValidationError):
        await ArchitectAgent().plan("too short")


async def test_missing_gateway_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        await ArchitectAgent().plan(OBJECTIVE)


async def test_missing_dspy_raises_and_does_not_fall_back() -> None:
    architect = ArchitectAgent().bind(gateway=MockLM())
    with mock.patch.dict(sys.modules, {"dspy": None}), pytest.raises(MissingExtraError):
        await architect.plan(OBJECTIVE)


# --- reasoning (dspy) ---------------------------------------------------------------------------


async def test_structured_reply_yields_a_multi_agent_plan() -> None:
    pytest.importorskip("dspy")
    architect = ArchitectAgent().bind(gateway=MockLM(responses={"korch-default": _STRUCTURED}))
    plan = await architect.plan(OBJECTIVE, intent="summarize", difficulty="moderate")
    assert isinstance(plan, ExecutionPlan)
    assert [c.id for c in plan.agents] == ["researcher", "writer"]
    assert plan.rationale == "split the work"
    assert plan.intent == "summarize"


async def test_reasoning_failure_falls_back_to_a_single_agent_plan() -> None:
    pytest.importorskip("dspy")

    class _Boom:
        async def complete(
            self, messages: object, *, model: str, max_tokens: int | None = None
        ) -> object:
            raise RuntimeError("gateway exploded")

        async def available_models(self) -> list[object]:
            return []

    plan = await ArchitectAgent().bind(gateway=_Boom()).plan(OBJECTIVE, difficulty="complex")
    assert [c.id for c in plan.agents] == ["worker"]
    assert plan.difficulty == "complex"
    assert "Fallback" in plan.rationale


async def test_a_structured_reply_with_no_valid_roles_falls_back_to_a_single_agent_plan() -> None:
    # _reason_plan raises ValidationError internally when roles parse to nothing, but plan()'s
    # own `except Exception` catches everything non-MissingExtraError and falls back — the same
    # observable outcome as a raising gateway (test_reasoning_failure_falls_back_...), just
    # reached through the "reply parsed but was unusable" path instead of a hard failure.
    pytest.importorskip("dspy")
    empty_roles = "[[ ## roles ## ]]\n!!!\n\n[[ ## rationale ## ]]\nnone\n\n[[ ## completed ## ]]"
    architect = ArchitectAgent().bind(gateway=MockLM(responses={"korch-default": empty_roles}))
    plan = await architect.plan(OBJECTIVE)
    assert [c.id for c in plan.agents] == ["worker"]
    assert "Fallback" in plan.rationale


@pytest.mark.parametrize(
    ("given", "expected"),
    [("trivial", "trivial"), ("complex", "complex"), ("nonsense", "moderate")],
)
async def test_difficulty_normalises_known_values_and_falls_back_to_moderate(
    given: str, expected: str
) -> None:
    pytest.importorskip("dspy")
    architect = ArchitectAgent().bind(gateway=MockLM(responses={"korch-default": _STRUCTURED}))
    plan = await architect.plan(OBJECTIVE, difficulty=given)
    assert plan.difficulty == expected


async def test_planning_is_deterministic_under_mock() -> None:
    pytest.importorskip("dspy")
    gateway = MockLM(responses={"korch-default": _STRUCTURED})
    first = await ArchitectAgent().bind(gateway=gateway).plan(OBJECTIVE)
    second = await ArchitectAgent().bind(gateway=gateway).plan(OBJECTIVE)
    assert first == second
