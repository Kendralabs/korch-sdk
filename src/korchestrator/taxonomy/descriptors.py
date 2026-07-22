"""Cognitive layer (L2). Imports: models, stdlib. No optional dependency.

The default catalogue of :class:`~korchestrator.models.agent.AgentDescriptor`s — what each built-in
agent kind is good at — used by the Architect and the router to match intents to agents. The
catalogue is data, not behaviour; ``AgentDescriptor`` is a ``0.x`` shape that may change (spec 05).
"""

from __future__ import annotations

from korchestrator.models.agent import AgentDescriptor

__all__ = ["default_descriptors", "descriptors_for_intent"]

_DEFAULT_DESCRIPTORS: tuple[AgentDescriptor, ...] = (
    AgentDescriptor(
        id="researcher",
        description="Gathers and synthesises information from the objective and context.",
        capabilities=("research", "summarization"),
        intents=("research", "summarize", "analyze"),
    ),
    AgentDescriptor(
        id="writer",
        description="Drafts and refines written content.",
        capabilities=("writing", "summarization"),
        intents=("generate", "summarize"),
    ),
    AgentDescriptor(
        id="analyst",
        description="Analyses, evaluates, and extracts structure from information.",
        capabilities=("analysis", "extraction"),
        intents=("analyze", "extract"),
    ),
    AgentDescriptor(
        id="coder",
        description="Writes, reviews, and debugs code.",
        capabilities=("code-generation",),
        intents=("code",),
    ),
    AgentDescriptor(
        id="planner",
        description="Decomposes goals into an ordered plan of work.",
        capabilities=("planning",),
        intents=("plan",),
    ),
    AgentDescriptor(
        id="generalist",
        description="A capable all-round agent for objectives without a specific intent.",
        capabilities=("general",),
        intents=("general",),
    ),
)


def default_descriptors() -> tuple[AgentDescriptor, ...]:
    """Return the built-in agent descriptor catalogue."""
    return _DEFAULT_DESCRIPTORS


def descriptors_for_intent(intent: str) -> tuple[AgentDescriptor, ...]:
    """Return the descriptors that serve ``intent``, or the generalist if none match.

    Args:
        intent: The classified intent (e.g. ``"summarize"``).

    Returns:
        The matching :class:`AgentDescriptor`s, never empty — the generalist is the fallback.
    """
    matches = tuple(d for d in _DEFAULT_DESCRIPTORS if intent in d.intents)
    if matches:
        return matches
    return tuple(d for d in _DEFAULT_DESCRIPTORS if d.id == "generalist")
