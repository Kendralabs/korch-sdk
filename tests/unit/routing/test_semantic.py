"""Unit tests for the semantic router (spec 11 §190, P5.4) with a deterministic fake embedder."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from unittest import mock

import pytest

from korchestrator.config import Settings
from korchestrator.exceptions import MissingExtraError, RoutingError
from korchestrator.models.routing import ModelCard, RoutingContext, TaskSemantics
from korchestrator.routing import get_router
from korchestrator.routing.semantic import SemanticRouter, make_embedder


class FakeEmbedder:
    """A deterministic offline embedder: a 2-D vector by keyword, tracking what it embedded."""

    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        self.embedded.extend(texts)
        return [(float("code" in t), float("summar" in t)) for t in texts]


def _card(name: str, description: str) -> ModelCard:
    return ModelCard(
        name=name,
        provider="p",
        description=description,
        context_window=1000,
        cost_per_1k_input_usd=0.0,
        cost_per_1k_output_usd=0.0,
        latency_p50_ms=1,
        quality_score=0.5,
    )


_CODER = _card("coder", "writes and reviews code")
_SUMMARIZER = _card("summarizer", "summarizes long documents")


def _ctx(intent: str) -> RoutingContext:
    return RoutingContext(
        agent_id="w",
        task=TaskSemantics(intent=intent, difficulty="moderate"),
        candidates=(_CODER, _SUMMARIZER),
    )


async def test_selects_the_most_similar_description() -> None:
    result = await SemanticRouter(FakeEmbedder()).select_model(_ctx("code"))
    assert result.model_name == "coder"
    assert result.strategy == "semantic"
    assert 0.0 <= result.score <= 1.0


async def test_precomputed_task_embedding_is_used() -> None:
    ctx = RoutingContext(
        agent_id="w",
        task=TaskSemantics(intent="x", difficulty="moderate", embedding=(0.0, 1.0)),
        candidates=(_CODER, _SUMMARIZER),
    )
    result = await SemanticRouter(FakeEmbedder()).select_model(ctx)
    assert result.model_name == "summarizer"


async def test_no_candidates_raises() -> None:
    ctx = RoutingContext(agent_id="w", task=TaskSemantics(intent="code", difficulty="moderate"))
    with pytest.raises(RoutingError) as info:
        await SemanticRouter(FakeEmbedder()).select_model(ctx)
    assert info.value.code == "ROUTING_NO_CANDIDATES"


async def test_card_embeddings_are_cached_until_the_ttl_expires() -> None:
    now = [0.0]
    embedder = FakeEmbedder()
    router = SemanticRouter(embedder, ttl_seconds=100, time_source=lambda: now[0])

    await router.select_model(_ctx("code"))
    after_first = len(embedder.embedded)  # task text + two card descriptions
    assert after_first == 3

    await router.select_model(_ctx("code"))  # same time: everything cached, nothing re-embedded
    assert len(embedder.embedded) == after_first

    now[0] = 200.0  # past the TTL
    await router.select_model(_ctx("code"))
    assert len(embedder.embedded) == after_first * 2  # re-embedded after expiry


async def test_get_router_semantic_uses_an_injected_embedder() -> None:
    router = get_router(Settings(routing_strategy="semantic"), embedder=FakeEmbedder())
    result = await router.select_model(_ctx("code"))
    assert result.model_name == "coder"


def test_make_embedder_without_the_extra_raises_missing_extra() -> None:
    with (
        mock.patch.dict(sys.modules, {"sentence_transformers": None}),
        pytest.raises(MissingExtraError),
    ):
        make_embedder(Settings())


def test_get_router_semantic_without_the_extra_raises_missing_extra() -> None:
    # No injected embedder + no [routing] extra → an actionable MissingExtraError at build time.
    with (
        mock.patch.dict(sys.modules, {"sentence_transformers": None}),
        pytest.raises(MissingExtraError),
    ):
        get_router(Settings(routing_strategy="semantic"))
