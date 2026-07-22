"""Cognitive layer (L2). Imports: core, models, exceptions, stdlib, pydantic. No dspy.

The unified ``Agent`` — the one agent type users touch. Constructed declaratively
(``Agent(id="lead", role="review-lead")``) it is a swarm vertex the framework reasons for;
subclassed with a ``think`` override it is a fully custom agent. Either way it obeys the
**frozen-snapshot contract** (spec 06 §5): ``think`` receives an immutable ``AgentState`` and
returns a ``StateUpdate`` delta — it never mutates shared state and never reads the wall clock,
using the injected ``self.clock`` instead. See ADR 0012 for why the declarative and behavioural
agents are one class rather than two.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pydantic import ValidationError as PydanticValidationError
from typing_extensions import Self

from korchestrator.core.graph import Node
from korchestrator.exceptions import ConfigurationError, ValidationError
from korchestrator.interfaces import IModelGateway
from korchestrator.models.agent import AgentConfig, AgentPersona
from korchestrator.models.state import AgentState, StateUpdate

__all__ = ["Agent"]

# The kernel's replay-safe clock is a zero-argument callable; agents use it as ``self.clock.now()``.
Clock = Callable[[], datetime]


class _BoundClock:
    """Adapts the kernel's ``Callable[[], datetime]`` clock to the ``clock.now()`` agents call."""

    __slots__ = ("_now_fn",)

    def __init__(self, now_fn: Clock) -> None:
        """Wrap the injected zero-argument clock callable."""
        self._now_fn = now_fn

    def now(self) -> datetime:
        """Return the injected clock's current, replay-safe time."""
        return self._now_fn()


class Agent:
    """A single agent in a swarm — declarative by default, subclassable for custom behaviour.

    Construct it declaratively and the framework supplies the reasoning::

        Agent(id="security", role="security-reviewer", model="gpt-4o")

    or subclass it and override :meth:`think` for a fully custom agent::

        class WordCountAgent(Agent):
            async def think(self, state: AgentState) -> StateUpdate:
                ...

    Frozen-snapshot contract (spec 06 §5): :meth:`think` MUST NOT mutate ``state`` (it is a frozen
    model, so mutation raises), MUST NOT call ``datetime.now()`` — use :attr:`clock` — MUST NOT read
    another agent's output from the same superstep, and MUST return within ``timeout_seconds``.
    Returning ``halt=True`` permanently deactivates the node.

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

    Raises:
        ValidationError: If any input fails validation (e.g. an ``id`` that does not match the
            allowed pattern). Always ``korchestrator.ValidationError`` — no raw pydantic error
            escapes (spec 08 §2.2).

    Example:
        >>> from korchestrator import Agent
        >>> agent = Agent(id="lead", role="review-lead")
        >>> agent.id
        'lead'
        >>> agent.config.persona.role
        'review-lead'
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
        """Validate the inputs into an immutable :class:`AgentConfig`; start with no clock bound."""
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
        self._clock: _BoundClock | None = None
        self._gateway: IModelGateway | None = None

    @property
    def id(self) -> str:
        """The agent's identifier."""
        return self._config.id

    @property
    def persona(self) -> AgentPersona:
        """The agent's static persona."""
        return self._config.persona

    @property
    def config(self) -> AgentConfig:
        """The immutable :class:`AgentConfig` this agent was validated into."""
        return self._config

    @property
    def clock(self) -> _BoundClock:
        """The injected replay-safe clock; use ``self.clock.now()`` inside :meth:`think`.

        Raises:
            ConfigurationError: If no clock has been bound. The runtime binds one via :meth:`bind`
                before a run; in a unit test, call ``agent.bind(clock=FakeClock())`` first.
        """
        if self._clock is None:
            raise ConfigurationError(
                f"Agent {self.id!r} has no clock bound. The runtime binds a replay-safe clock "
                "before the run; in a test, call bind(clock=...) first."
            )
        return self._clock

    def bind(self, *, clock: Clock, gateway: IModelGateway | None = None) -> Self:
        """Inject the replay-safe ``clock`` (and optionally the model ``gateway``); return ``self``.

        Called by the composition root before a run. The clock is the same injected
        ``Callable[[], datetime]`` the kernel uses, so an agent's timestamps stay replay-safe. The
        gateway is used by reasoning agents (e.g. :class:`~korchestrator.agents.WorkerAgent`);
        agents that do not reason ignore it.
        """
        self._clock = _BoundClock(clock)
        if gateway is not None:
            self._gateway = gateway
        return self

    def to_node(self) -> Node:
        """Materialise this agent as a kernel :class:`~korchestrator.core.graph.Node`.

        Returns:
            A :class:`Node` binding this agent's :class:`AgentConfig` to its :meth:`think` callable,
            ready to place in an :class:`~korchestrator.core.graph.AgentGraph`.
        """
        return Node(config=self._config, compute=self.think)

    def is_complete(self, state: AgentState) -> bool:
        """Whether this agent considers its work finished, given ``state``.

        The default is ``False``; reasoning agents override it to signal they have reached a final
        answer and should halt. It never mutates ``state``.
        """
        return False

    async def think(self, state: AgentState) -> StateUpdate:
        """Turn a frozen ``state`` snapshot into this agent's :class:`StateUpdate` delta.

        The base implementation raises — a declaratively-constructed agent has no reasoning of its
        own until the façade supplies the default reasoning agent (P4.9), and a custom agent must
        override this method.

        Args:
            state: An immutable snapshot of the shared state. MUST NOT be mutated.

        Returns:
            This agent's :class:`StateUpdate` delta for the current superstep.
        """
        raise NotImplementedError(
            f"Agent {self.id!r} has no think() implementation. Subclass Agent and override "
            "think(), or run it through Korch/Swarm, which supplies the default reasoning agent."
        )
