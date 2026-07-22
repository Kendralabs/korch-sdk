"""Cognitive layer (L2). Imports: interfaces, models, exceptions, stdlib; [routing] extra (lazy).

The semantic routing strategy: embed the task and each candidate's description, and pick the model
whose description is most similar. Embeddings are the only part that needs the ``[routing]`` extra;
it is imported lazily inside :func:`make_embedder`, so a base install that never selects the
semantic strategy stays dependency-free. Card embeddings are cached with a configured TTL behind an
injected time source (a composition-time concern, never workflow scope), so expiry is deterministic.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from korchestrator.constants import error_codes as codes
from korchestrator.exceptions import MissingExtraError, RoutingError
from korchestrator.models.routing import ModelCard, RoutingContext, RoutingResult, TaskSemantics

__all__ = ["DEFAULT_EMBEDDING_MODEL", "Embedder", "SemanticRouter", "make_embedder"]

# A small, widely available sentence-embedding model used when EMBEDDING_PROVIDER is unset.
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@runtime_checkable
class Embedder(Protocol):
    """Turn texts into dense vectors — the one structural contract the semantic strategy needs."""

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Return one vector per input text, in order."""
        ...


class SemanticRouter:
    """Select the model whose description best matches the task, by embedding similarity.

    Args:
        embedder: The embedding backend. Inject a deterministic fake in tests; production uses
            :func:`make_embedder` (the ``[routing]`` extra).
        ttl_seconds: How long a card-description embedding stays cached. Defaults to ``900``.
        time_source: Monotonic seconds source for cache expiry; injected for deterministic tests.

    Example:
        >>> import asyncio
        >>> from korchestrator.models.routing import ModelCard, RoutingContext, TaskSemantics
        >>> from korchestrator.routing.semantic import SemanticRouter
        >>> class Toy:
        ...     def embed(self, texts):
        ...         return [(float("code" in t), float("write" in t)) for t in texts]
        >>> coder = ModelCard(
        ...     name="coder", provider="p", description="writes code", context_window=1000,
        ...     cost_per_1k_input_usd=0.0, cost_per_1k_output_usd=0.0, latency_p50_ms=1,
        ...     quality_score=0.5,
        ... )
        >>> ctx = RoutingContext(
        ...     agent_id="w",
        ...     task=TaskSemantics(intent="code", difficulty="moderate"),
        ...     candidates=(coder,),
        ... )
        >>> asyncio.run(SemanticRouter(Toy()).select_model(ctx)).strategy
        'semantic'
    """

    def __init__(
        self,
        embedder: Embedder,
        *,
        ttl_seconds: int = 900,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        """Wrap the embedder in a TTL cache for card-description vectors."""
        self._cache = _EmbeddingCache(embedder, ttl_seconds=ttl_seconds, time_source=time_source)

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        """Embed the task and candidates and return the most similar model."""
        if not context.candidates:
            raise RoutingError(
                f"The semantic strategy needs candidate models for agent {context.agent_id!r}, but "
                "none were supplied. Configure MODELCARD_SOURCE.",
                code=codes.ROUTING_NO_CANDIDATES,
            )
        best, similarity = await asyncio.to_thread(self._rank, context)
        score = max(0.0, min(1.0, (similarity + 1.0) / 2.0))  # cosine [-1, 1] → [0, 1]
        return RoutingResult(
            model_name=best.name,
            strategy="semantic",
            score=round(score, 6),
            reason=f"description of {best.name!r} best matched the task (cosine {similarity:.3f})",
            fallbacks=best.fallbacks,
        )

    def _rank(self, context: RoutingContext) -> tuple[ModelCard, float]:
        task_vector = self._task_vector(context.task)
        card_vectors = self._cache.embed([card.description for card in context.candidates])
        ranked = sorted(
            (
                (_cosine(task_vector, vector), card.name, card)
                for vector, card in zip(card_vectors, context.candidates, strict=True)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        similarity, _, best = ranked[0]
        return best, similarity

    def _task_vector(self, task: TaskSemantics) -> tuple[float, ...]:
        if task.embedding is not None:
            return task.embedding
        text = " ".join((task.intent, *task.required_capabilities))
        return self._cache.embed([text])[0]


class _EmbeddingCache:
    """Cache embeddings by text with a per-entry TTL, using an injected monotonic time source."""

    def __init__(
        self, embedder: Embedder, *, ttl_seconds: int, time_source: Callable[[], float]
    ) -> None:
        self._embedder = embedder
        self._ttl = float(ttl_seconds)
        self._time = time_source
        self._entries: dict[str, tuple[float, tuple[float, ...]]] = {}

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        now = self._time()
        missing = [text for text in dict.fromkeys(texts) if self._is_stale(text, now)]
        if missing:
            fresh = self._embedder.embed(missing)
            for text, vector in zip(missing, fresh, strict=True):
                self._entries[text] = (now + self._ttl, tuple(vector))
        return [self._entries[text][1] for text in texts]

    def _is_stale(self, text: str, now: float) -> bool:
        entry = self._entries.get(text)
        return entry is None or entry[0] <= now


def make_embedder(settings: object) -> Embedder:
    """Build the configured embedding backend, requiring the ``[routing]`` extra.

    Args:
        settings: A :class:`~korchestrator.config.Settings` whose ``embedding_provider`` names the
            model (falling back to :data:`DEFAULT_EMBEDDING_MODEL`).

    Returns:
        A ready :class:`Embedder`.

    Raises:
        MissingExtraError: If the ``[routing]`` extra (``sentence-transformers``) is not installed.
    """
    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        raise MissingExtraError(
            "The semantic routing strategy requires the 'routing' extra. "
            "Install it with: pip install 'korchestrator[routing]'"
        ) from exc
    provider = getattr(settings, "embedding_provider", None) or DEFAULT_EMBEDDING_MODEL
    return _SentenceTransformerEmbedder(provider)


class _SentenceTransformerEmbedder:
    """An :class:`Embedder` backed by a lazily loaded ``sentence-transformers`` model."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: object | None = None

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        model = self._load()
        vectors = model.encode(list(texts))  # type: ignore[attr-defined]
        return [tuple(float(value) for value in row) for row in vectors]

    def _load(self) -> object:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
