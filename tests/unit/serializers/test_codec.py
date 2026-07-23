"""Unit tests for the JSON codec (spec 08 §6, P8.5, ADR 0017).

Golden fixtures live in ``tests/fixtures/serde/`` and are compared byte-for-byte — an accidental
ordering or formatting change fails the build (spec 08 §6.7).
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pytest

from korchestrator.exceptions import ValidationError
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.plan import ExecutionPlan, TaskDecomposition
from korchestrator.models.result import RunResult
from korchestrator.models.routing import ModelCard
from korchestrator.models.state import AgentState, Message, RunStatus
from korchestrator.serializers import from_json, to_json

NOW = datetime(2026, 7, 23, 10, 30, 45, 123456, tzinfo=timezone.utc)
FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "serde"


def _state() -> AgentState:
    return AgentState(
        run_id="r1",
        tenant_id="acme",
        objective="summarize the quarterly report",
        messages=(
            Message(
                id="r1:0:lead:0",
                sender="lead",
                content="done",
                kind="answer",
                superstep=0,
                valid_time=NOW,
            ),
        ),
        superstep=1,
        trust_score=0.9,
        transaction_time=NOW,
    )


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        objective="summarize the quarterly report",
        intent="summarize",
        difficulty="moderate",
        agents=(AgentConfig(id="lead", persona=AgentPersona(role="lead")),),
        edges=(("lead", "lead2"),),
        tasks=(TaskDecomposition(task_id="t1", description="d", assigned_agent="lead"),),
        rationale="because",
    )


def _card() -> ModelCard:
    return ModelCard(
        name="gpt-4o-mini",
        provider="openai",
        description="fast, cheap",
        capabilities=("chat", "tools"),
        context_window=128000,
        cost_per_1k_input_usd=0.00015,
        cost_per_1k_output_usd=0.0006,
        latency_p50_ms=400,
        quality_score=0.8,
    )


def _result() -> RunResult:
    state = _state()
    return RunResult(
        run_id="r1",
        status=RunStatus.COMPLETED,
        final_answer="done",
        supersteps=1,
        messages=state.messages,
        state=state,
        trust_score=0.9,
        started_at=NOW,
        completed_at=NOW,
    )


_GOLDEN = {
    "agent_state.json": _state,
    "execution_plan.json": _plan,
    "model_card.json": _card,
    "run_result.json": _result,
}


@pytest.mark.parametrize("filename", sorted(_GOLDEN))
def test_to_json_matches_the_golden_fixture_byte_for_byte(filename: str) -> None:
    build = _GOLDEN[filename]
    golden = (FIXTURES / filename).read_text(encoding="utf-8")
    assert to_json(build()) == golden


@pytest.mark.parametrize(
    "build", [_state, _plan, _card, _result], ids=["state", "plan", "card", "result"]
)
def test_to_json_is_deterministic(build: object) -> None:
    model = build()  # type: ignore[operator]
    assert to_json(model) == to_json(model)


@pytest.mark.parametrize(
    ("build", "model_cls"),
    [(_state, AgentState), (_plan, ExecutionPlan), (_card, ModelCard), (_result, RunResult)],
    ids=["state", "plan", "card", "result"],
)
def test_round_trip_equals_the_original(build: object, model_cls: type) -> None:
    model = build()  # type: ignore[operator]
    assert from_json(to_json(model), model_cls) == model  # type: ignore[arg-type]


def test_the_envelope_carries_the_schema_and_package_version() -> None:
    envelope = json.loads(to_json(_card()))
    assert envelope["schema_version"] == 1
    assert envelope["type"] == "ModelCard"
    assert isinstance(envelope["korchestrator_version"], str) and envelope["korchestrator_version"]


def test_timestamps_are_iso8601_with_utc_offset_and_microseconds() -> None:
    envelope = json.loads(to_json(_state()))
    assert envelope["data"]["transaction_time"] == "2026-07-23T10:30:45.123456Z"


# --- errors -----------------------------------------------------------------------------------


def test_to_json_rejects_an_unsupported_model() -> None:
    with pytest.raises(ValidationError):
        to_json(AgentConfig(id="lead", persona=AgentPersona(role="lead")))  # type: ignore[arg-type]


def test_from_json_rejects_an_unsupported_model_class() -> None:
    with pytest.raises(ValidationError):
        from_json(to_json(_card()), AgentConfig)


def test_from_json_rejects_malformed_json() -> None:
    with pytest.raises(ValidationError):
        from_json("{not json", ModelCard)


def test_from_json_rejects_a_non_envelope_payload() -> None:
    with pytest.raises(ValidationError):
        from_json(json.dumps({"name": "gpt-4o-mini"}), ModelCard)


def test_from_json_rejects_a_type_mismatch() -> None:
    with pytest.raises(ValidationError):
        from_json(to_json(_card()), AgentState)


def test_from_json_rejects_a_schema_version_newer_than_supported() -> None:
    envelope = json.loads(to_json(_card()))
    envelope["schema_version"] = 999
    with pytest.raises(ValidationError) as info:
        from_json(json.dumps(envelope), ModelCard)
    assert "999" in str(info.value)


def test_a_payload_missing_a_new_optional_field_still_loads() -> None:
    # spec 08 §6.6: an additive field (new, optional, with a default) does not bump
    # schema_version, and an old payload predating it must still load, picking up the default.
    envelope = json.loads(to_json(_card()))
    del envelope["data"]["fallbacks"]  # ModelCard.fallbacks: tuple[str, ...] = ()
    restored = from_json(json.dumps(envelope), ModelCard)
    assert restored.fallbacks == ()


def test_from_json_rejects_data_that_fails_model_validation() -> None:
    envelope = json.loads(to_json(_card()))
    del envelope["data"]["context_window"]  # a required field
    with pytest.raises(ValidationError):
        from_json(json.dumps(envelope), ModelCard)


# --- migration machinery (spec 08 §6.5) ---------------------------------------------------------


def test_a_lower_schema_version_with_no_registered_migration_is_rejected() -> None:
    # Nothing has evolved past v1 yet, so pretending a payload is v0 must fail loudly rather than
    # silently guessing at the missing migration.
    envelope = json.loads(to_json(_card()))
    envelope["schema_version"] = 0
    with pytest.raises(ValidationError) as info:
        from_json(json.dumps(envelope), ModelCard)
    assert "migration" in str(info.value).lower()


def test_a_registered_migration_is_applied_in_sequence() -> None:
    from korchestrator.serializers import codec

    def _v0_to_v1(data: dict) -> dict:
        return {**data, "quality_score": 0.5}

    codec._MIGRATIONS[(ModelCard, 0)] = _v0_to_v1
    try:
        envelope = json.loads(to_json(_card()))
        del envelope["data"]["quality_score"]
        envelope["schema_version"] = 0
        migrated = from_json(json.dumps(envelope), ModelCard)
        assert migrated.quality_score == 0.5
    finally:
        del codec._MIGRATIONS[(ModelCard, 0)]
