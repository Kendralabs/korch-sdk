"""Cognitive layer (L2). Imports: agents, interfaces, models, exceptions, stdlib. dspy is lazy.

``ArchitectAgent`` — the Architect meta-agent (spec 05 §36). Given an objective (and its classified
intent/difficulty), it reasons with the injected gateway to decompose the work into a small team of
agent roles and returns a validated :class:`~korchestrator.models.plan.ExecutionPlan`. On **any
reasoning failure** — a provider error, or a reply that yields no valid agent role (as a MockLM echo
does) — it returns a deterministic single-agent **mock plan**, so a swarm always gets a runnable
plan.

Requires the ``[dspy]`` extra: a missing extra raises ``MissingExtraError`` (it does *not* trigger
the mock-plan fallback, which is for reasoning failures, not a missing dependency — ADR 0013).
"""

from __future__ import annotations

import asyncio
import re
from typing import Literal

from typing_extensions import Self

from korchestrator.agents._reasoning import PLACEHOLDER_MODEL, predict_under_gateway
from korchestrator.agents.signatures import ArchitectSignature, Signature, load_dspy
from korchestrator.exceptions import ConfigurationError, MissingExtraError, ValidationError
from korchestrator.interfaces import IModelGateway
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.plan import ExecutionPlan

__all__ = ["ArchitectAgent"]

_Difficulty = Literal["trivial", "moderate", "complex"]
_MAX_PLAN_AGENTS = 8


class ArchitectAgent:
    """Decompose an objective into a validated :class:`ExecutionPlan`, with a mock-plan fallback.

    Bind the model gateway (``bind(gateway=...)``), then call :meth:`plan`. Reasoning runs on a
    worker thread; a failure (or an unusable reply) falls back to a deterministic single-agent plan.

    Args:
        signature: The planning :class:`~korchestrator.agents.signatures.Signature`; defaults to
            :class:`~korchestrator.agents.signatures.ArchitectSignature`.

    Example:
        >>> from korchestrator.agents.architect import ArchitectAgent
        >>> architect = ArchitectAgent()  # doctest: +SKIP
    """

    def __init__(self, *, signature: type[Signature] = ArchitectSignature) -> None:
        """Record the planning signature; start with no gateway bound."""
        self._signature = signature
        self._gateway: IModelGateway | None = None

    def bind(self, *, gateway: IModelGateway) -> Self:
        """Inject the model ``gateway`` used for planning; return ``self`` for chaining."""
        self._gateway = gateway
        return self

    async def plan(
        self,
        objective: str,
        *,
        intent: str = "general",
        difficulty: str = "moderate",
        max_supersteps: int = 10,
    ) -> ExecutionPlan:
        """Produce an :class:`ExecutionPlan` for ``objective``; fall back to a mock plan on failure.

        Args:
            objective: The goal, at least 10 characters.
            intent: The classified intent (from the taxonomy); defaults to ``"general"``.
            difficulty: ``"trivial"`` / ``"moderate"`` / ``"complex"``; unknown values become
                ``"moderate"``.
            max_supersteps: The plan's halt bound (1-100). Defaults to 10.

        Returns:
            A validated :class:`ExecutionPlan` with at least one agent.

        Raises:
            ValidationError: If ``objective`` is shorter than 10 characters.
            ConfigurationError: If no model gateway has been bound.
            MissingExtraError: If the ``[dspy]`` extra is not installed.
        """
        if len(objective) < 10:
            raise ValidationError(
                f"Objective must be at least 10 characters, got {len(objective)}. "
                "Describe the goal in a sentence."
            )
        gateway = self._require_gateway()
        try:
            return await asyncio.to_thread(
                self._reason_plan, objective, intent, difficulty, max_supersteps, gateway
            )
        except MissingExtraError:
            raise
        except Exception:
            return self._mock_plan(objective, intent, difficulty, max_supersteps)

    def _reason_plan(
        self,
        objective: str,
        intent: str,
        difficulty: str,
        max_supersteps: int,
        gateway: IModelGateway,
    ) -> ExecutionPlan:
        """Reason a plan (synchronous; called via a thread). Raises on an unusable reply."""
        dspy = load_dspy()  # MissingExtraError propagates past the fallback (ADR 0013)
        result = predict_under_gateway(
            dspy,
            self._signature,
            gateway=gateway,
            model=PLACEHOLDER_MODEL,
            inputs={"objective": objective, "intent": intent, "difficulty": difficulty},
        )
        agents = _agents_from_roles(str(getattr(result, "roles", "")))
        if not agents:
            raise ValidationError("Planning produced no valid agent roles.")
        return ExecutionPlan(
            objective=objective,
            intent=intent,
            difficulty=_normalise_difficulty(difficulty),
            agents=agents,
            max_supersteps=max_supersteps,
            rationale=str(getattr(result, "rationale", "")),
        )

    def _mock_plan(
        self, objective: str, intent: str, difficulty: str, max_supersteps: int
    ) -> ExecutionPlan:
        """A deterministic single generalist-agent plan used when reasoning is unusable."""
        return ExecutionPlan(
            objective=objective,
            intent=intent,
            difficulty=_normalise_difficulty(difficulty),
            agents=(AgentConfig(id="worker", persona=AgentPersona(role="generalist")),),
            max_supersteps=max_supersteps,
            rationale="Fallback single-agent plan (reasoning unavailable or unusable).",
        )

    def _require_gateway(self) -> IModelGateway:
        if self._gateway is None:
            raise ConfigurationError(
                "ArchitectAgent has no model gateway bound. Call bind(gateway=...) before planning "
                "(the composition root does this)."
            )
        return self._gateway


def _agents_from_roles(roles_text: str) -> tuple[AgentConfig, ...]:
    """Parse a newline-separated roles list into unique, valid :class:`AgentConfig`s (bounded)."""
    configs: list[AgentConfig] = []
    seen: set[str] = set()
    for line in roles_text.splitlines():
        role = line.strip(" -*\t")
        slug = _slug(role)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        configs.append(AgentConfig(id=slug, persona=AgentPersona(role=role[:200])))
        if len(configs) >= _MAX_PLAN_AGENTS:
            break
    return tuple(configs)


def _slug(text: str) -> str:
    """Slugify a role into a valid AgentConfig id (``^[a-z0-9][a-z0-9_-]{0,63}$``) or ``""``."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
    return slug if slug and slug[0].isalnum() else ""


def _normalise_difficulty(value: str) -> _Difficulty:
    match value.strip().lower():
        case "trivial":
            return "trivial"
        case "complex":
            return "complex"
        case _:
            return "moderate"
