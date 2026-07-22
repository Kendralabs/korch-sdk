"""Unit tests for the model-card catalogue and loader (P5.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError
from korchestrator.routing.model_cards import builtin_model_cards, load_model_cards


def test_builtin_catalogue_is_nonempty_and_named() -> None:
    names = {card.name for card in builtin_model_cards()}
    assert "gpt-4o" in names
    assert len(names) == len(builtin_model_cards())  # unique names


def test_load_defaults_to_builtin() -> None:
    assert load_model_cards(Settings()) == builtin_model_cards()


def test_load_from_file(tmp_path: Path) -> None:
    card = {
        "name": "local-model",
        "provider": "local",
        "description": "a local model",
        "context_window": 8192,
        "cost_per_1k_input_usd": 0.0,
        "cost_per_1k_output_usd": 0.0,
        "latency_p50_ms": 10,
        "quality_score": 0.5,
    }
    path = tmp_path / "cards.json"
    path.write_text(json.dumps([card]), encoding="utf-8")
    cards = load_model_cards(Settings(modelcard_source="file", modelcard_path=str(path)))
    assert len(cards) == 1
    assert cards[0].name == "local-model"


def test_file_source_without_path_raises() -> None:
    with pytest.raises(ConfigurationError):
        load_model_cards(Settings(modelcard_source="file"))


def test_file_source_with_bad_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not an array}", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_model_cards(Settings(modelcard_source="file", modelcard_path=str(path)))


def test_url_source_is_deferred() -> None:
    with pytest.raises(ConfigurationError) as info:
        load_model_cards(Settings(modelcard_source="url", modelcard_url="https://example/x"))
    assert "url" in info.value.message.lower()
