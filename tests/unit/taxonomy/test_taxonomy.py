"""Unit tests for the deterministic taxonomy (spec 05 §31, P4.8)."""

from __future__ import annotations

import pytest

from korchestrator.models.routing import TaskSemantics
from korchestrator.taxonomy import (
    TaxonomyClassifier,
    default_descriptors,
    descriptors_for_intent,
)


@pytest.mark.parametrize(
    ("objective", "intent"),
    [
        ("Summarize the Q3 incident reports", "summarize"),
        ("Research the market for durable execution engines", "research"),
        ("Analyze and compare the two proposals", "analyze"),
        ("Implement a retry decorator with backoff", "code"),
        ("Design a plan for the migration", "plan"),
        ("Write a launch announcement", "generate"),
        ("Say hello to the team", "general"),
    ],
)
def test_intent_classification(objective: str, intent: str) -> None:
    assert TaxonomyClassifier().classify(objective).intent == intent


def test_classification_is_deterministic_and_typed() -> None:
    classifier = TaxonomyClassifier()
    objective = "Summarize the Q3 incident reports clearly"
    first = classifier.classify(objective)
    second = classifier.classify(objective)
    assert isinstance(first, TaskSemantics)
    assert first == second
    assert first.required_capabilities == ("summarization",)
    assert first.estimated_input_tokens > 0


@pytest.mark.parametrize(
    ("objective", "difficulty"),
    [
        ("Reverse a string", "trivial"),
        ("Summarize the Q3 incident reports for the board", "moderate"),
        ("Research and integrate findings across each regional report end-to-end", "complex"),
    ],
)
def test_difficulty_heuristic(objective: str, difficulty: str) -> None:
    assert TaxonomyClassifier().classify(objective).difficulty == difficulty


def test_default_descriptors_are_nonempty_and_include_the_generalist() -> None:
    ids = {d.id for d in default_descriptors()}
    assert "generalist" in ids
    assert len(ids) == len(default_descriptors())  # unique ids


def test_descriptors_for_intent_matches_or_falls_back() -> None:
    assert {d.id for d in descriptors_for_intent("code")} == {"coder"}
    # An unknown intent falls back to the generalist, never empty.
    fallback = descriptors_for_intent("no-such-intent")
    assert [d.id for d in fallback] == ["generalist"]
