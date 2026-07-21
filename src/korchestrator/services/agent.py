"""Façade layer (composition root). Imports: korchestrator.models.

The user-facing ``Agent`` builder — a thin, typed constructor that produces the internal
``AgentConfig`` model. Users author ``Agent``; the kernel consumes ``AgentConfig``.
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from korchestrator.exceptions import ValidationError
from korchestrator.models.agent import AgentConfig, AgentPersona

__all__ = ["Agent"]


class Agent:
    """A single agent in a swarm, authored by the user.

    A thin wrapper that validates its inputs into an immutable :class:`AgentConfig`. Constructing
    an ``Agent`` performs no execution — it only builds the configuration the kernel will run.

    Args:
        id: The agent's identifier, matching ``^[a-z0-9][a-z0-9_-]{0,63}$``.
        role: The persona's role, e.g. ``"security-reviewer"``.
        model: The model to route this agent to, or ``None`` to let routing decide.
        tools: Names of tools mounted on this agent.
        goal: The persona's goal.
        backstory: The persona's backstory.
        max_react_steps: Bound on the ReAct loop, 0-10.
        hitl_threshold: Per-agent trust threshold for human-in-the-loop, 0.0-1.0, or ``None``.
        timeout_seconds: Per-agent wall-clock budget.

    Example:
        >>> from korchestrator import Agent
        >>> agent = Agent(id="lead", role="review-lead")
        >>> agent.id
        'lead'
        >>> agent.config.persona.role
        'review-lead'

    Raises:
        ValidationError: If any input fails validation (e.g. an ``id`` that does not match the
            allowed pattern). This is ``korchestrator.ValidationError`` — the façade never lets a
            raw pydantic error escape (spec 08 §2.2, §7).
    """

    def __init__(
        self,
        id: str,  # noqa: A002 — the public field is named `id`, matching AgentConfig (spec 04)
        *,
        role: str,
        model: str | None = None,
        tools: tuple[str, ...] = (),
        goal: str = "",
        backstory: str = "",
        max_react_steps: int = 3,
        hitl_threshold: float | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        """Validate the inputs into an immutable :class:`AgentConfig`."""
        try:
            self._config = AgentConfig(
                id=id,
                persona=AgentPersona(role=role, goal=goal, backstory=backstory),
                model=model,
                tools=tools,
                max_react_steps=max_react_steps,
                hitl_threshold=hitl_threshold,
                timeout_seconds=timeout_seconds,
            )
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Invalid agent configuration for id={id!r}: {exc}. "
                "Check the id pattern (^[a-z0-9][a-z0-9_-]{0,63}$), the numeric bounds, and role.",
                code="KORCH_VALIDATION_FAILED",
            ) from exc

    @property
    def id(self) -> str:
        """The agent's identifier."""
        return self._config.id

    @property
    def config(self) -> AgentConfig:
        """The immutable :class:`AgentConfig` this agent was validated into."""
        return self._config
