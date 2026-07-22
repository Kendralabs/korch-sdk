"""Adapter layer.

Allowed imports (beyond stdlib + pydantic): core, interfaces, models, config, exceptions,
logging; temporalio lazy in temporal_runtime.py only ([temporal] extra). Implements
IDurableRuntime twice: in-process local_runtime and durable temporal_runtime, selected by config.
"""

from __future__ import annotations

from korchestrator.config import Settings
from korchestrator.core.channels import ChannelSchema
from korchestrator.core.graph import AgentGraph
from korchestrator.core.pregel import Clock, SuperstepObserver
from korchestrator.exceptions import MissingExtraError
from korchestrator.interfaces.runtime import IDurableRuntime
from korchestrator.runtime.local_runtime import LocalRuntime

__all__ = ["LocalRuntime", "resolve_runtime"]


def resolve_runtime(
    settings: Settings,
    graph: AgentGraph,
    *,
    clock: Clock,
    channels: ChannelSchema | None = None,
    observer: SuperstepObserver | None = None,
) -> IDurableRuntime:
    """Select and construct the durable runtime from ``settings.korch_runtime``.

    This is the one place a ``KORCH_RUNTIME`` config value becomes a concrete runtime (spec 03 §5).
    ``"local"`` is the zero-infrastructure default; ``"temporal"`` needs the ``[temporal]`` extra.

    Args:
        settings: The resolved settings; ``korch_runtime`` selects the adapter, and
            ``governance_trust_threshold`` becomes the Temporal runtime's HITL fallback (spec 06
            §7) — this stays the one place that value is read from ``Settings`` (B6).
        graph: The validated agent graph the runtime will run.
        clock: The injected, replay-safe clock.
        channels: The channel-to-reducer bindings. Defaults to all-``LastValue``.
        observer: Optional superstep observer (middleware/event hooks). Honoured by the local
            runtime; Temporal hook dispatch runs in activities and is deferred to a later phase.

    Returns:
        A constructed :class:`~korchestrator.interfaces.IDurableRuntime`.

    Raises:
        MissingExtraError: If ``"temporal"`` is selected without the ``[temporal]`` extra.

    Example:
        >>> from korchestrator.config import Settings
        >>> from korchestrator.core import AgentGraph, Node
        >>> from korchestrator.models.agent import AgentConfig, AgentPersona
        >>> from korchestrator.runtime import LocalRuntime, resolve_runtime
        >>> async def _noop(state):
        ...     raise NotImplementedError
        >>> cfg = AgentConfig(id="lead", persona=AgentPersona(role="lead"))
        >>> graph = AgentGraph([Node(cfg, _noop)])
        >>> runtime = resolve_runtime(Settings(korch_runtime="local"), graph, clock=lambda: None)
        >>> isinstance(runtime, LocalRuntime)
        True
    """
    if settings.korch_runtime == "local":
        return LocalRuntime(graph, clock=clock, channels=channels, observer=observer)
    # settings.korch_runtime is Literal["local", "temporal"]; the remaining case is "temporal".
    # temporal_runtime.py is imported lazily here — its module-top `import temporalio` means eager
    # import would break the base install; a missing [temporal] extra surfaces as ImportError.
    try:
        from korchestrator.runtime.temporal_runtime import TemporalRuntime
    except ImportError as exc:
        raise MissingExtraError(
            "The 'temporal' runtime requires the 'temporal' extra. "
            "Install it with: pip install 'korchestrator[temporal]'",
            code="KORCH_MISSING_EXTRA",
        ) from exc
    return TemporalRuntime(
        graph,
        clock=clock,
        channels=channels,
        global_threshold=settings.governance_trust_threshold,
    )
