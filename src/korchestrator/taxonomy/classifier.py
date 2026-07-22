"""Cognitive layer (L2). Imports: models, stdlib. No optional dependency.

A deterministic, dependency-free intent/difficulty classifier. It maps an objective to a
:class:`~korchestrator.models.routing.TaskSemantics` using keyword and length heuristics — no model
call, no ``[routing]`` extra — so classification is offline, fast, and reproducible. Semantic
(embedding-based) classification is a routing strategy that arrives with P5; this is the baseline
the Architect and router consume.
"""

from __future__ import annotations

from typing import Literal

from korchestrator.models.routing import TaskSemantics

__all__ = ["TaxonomyClassifier"]

_Difficulty = Literal["trivial", "moderate", "complex"]

# Intent vocabulary in priority order (first match wins), each with its trigger keywords and the
# capability it implies. Anything unmatched is the "general" intent.
_INTENTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("code", "code-generation", ("code", "implement", "debug", "refactor", "program", "function")),
    ("plan", "planning", ("plan", "design", "architect", "roadmap", "strategy", "decompose")),
    ("summarize", "summarization", ("summarize", "summarise", "summary", "recap", "brief")),
    ("research", "research", ("research", "investigate", "explore", "gather", "find out")),
    ("analyze", "analysis", ("analyze", "analyse", "assess", "evaluate", "review", "compare")),
    ("extract", "extraction", ("extract", "parse", "identify", "list")),
    ("generate", "writing", ("write", "generate", "draft", "create", "compose", "produce")),
)

# Phrases/words that signal a multi-part or cross-cutting objective.
_COMPLEX_SIGNALS: tuple[str, ...] = (
    "and then",
    "multiple",
    "each",
    "across",
    "integrate",
    "end-to-end",
    "several",
    "compare",
    "step by step",
)

_DEFAULT_OUTPUT_TOKENS = 256
_TOKENS_PER_WORD = 1.3


class TaxonomyClassifier:
    """Classify an objective into a :class:`TaskSemantics` with deterministic heuristics.

    The classifier is stateless and offline: the same objective always yields the same
    :class:`TaskSemantics`. Intent is the first keyword-matched category (else ``"general"``);
    difficulty is a length-and-signal heuristic.

    Example:
        >>> from korchestrator.taxonomy import TaxonomyClassifier
        >>> semantics = TaxonomyClassifier().classify("Summarize the Q3 incident reports")
        >>> semantics.intent
        'summarize'
        >>> semantics.difficulty
        'moderate'
    """

    def classify(self, objective: str) -> TaskSemantics:
        """Return the :class:`TaskSemantics` for ``objective``.

        Args:
            objective: The goal to classify.

        Returns:
            A :class:`TaskSemantics` with intent, difficulty, the implied required capability, and
            rough token estimates.
        """
        lowered = objective.lower()
        intent, capability = self._intent(lowered)
        words = len(objective.split())
        return TaskSemantics(
            intent=intent,
            difficulty=self._difficulty(lowered, words),
            required_capabilities=(capability,) if capability else (),
            estimated_input_tokens=int(words * _TOKENS_PER_WORD),
            estimated_output_tokens=_DEFAULT_OUTPUT_TOKENS,
        )

    @staticmethod
    def _intent(lowered: str) -> tuple[str, str]:
        for intent, capability, keywords in _INTENTS:
            if any(keyword in lowered for keyword in keywords):
                return intent, capability
        return "general", "general"

    @staticmethod
    def _difficulty(lowered: str, words: int) -> _Difficulty:
        if words > 40 or any(signal in lowered for signal in _COMPLEX_SIGNALS):
            return "complex"
        if words <= 4:
            return "trivial"
        return "moderate"
