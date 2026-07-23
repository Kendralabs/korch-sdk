"""Leaf-utility layer.

Allowed imports (beyond stdlib + pydantic): config, exceptions; OpenTelemetry packages lazy
([otel] extra). Every OTel import is confined **inside** ``_otel()`` below — never at module top
level — so importing this module (transitively, via ``korchestrator.services``) never touches OTel
and the base install stays ``pydantic``-only (CLAUDE.md §3, spec 08 §4).
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

from korchestrator.config import Settings, get_settings
from korchestrator.exceptions import MissingExtraError

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, UpDownCounter
    from opentelemetry.trace import Tracer

__all__ = ["Span", "is_enabled", "record_metric", "start_span"]

AttributeValue = str | bool | int | float

_METRIC_KINDS: dict[str, str] = {
    "korch.run.duration": "histogram",
    "korch.superstep.duration": "histogram",
    "korch.agents.active": "up_down_counter",
    "korch.tool.calls": "counter",
    "korch.model.tokens": "counter",
    "korch.run.status": "counter",
}
_INSTRUMENTS: dict[str, object] = {}


class Span(Protocol):
    """The subset of an OpenTelemetry span used across the telemetry boundary."""

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        """Attach one low-cardinality attribute to the current span."""


class _NoOpSpan:
    """Zero-overhead stand-in for a span: both the context manager and the yielded handle.

    ``start_span`` returns this same module-level instance every time telemetry is disabled — no
    context manager allocation, no OTel import (spec 08 §4).
    """

    __slots__ = ()

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        return None


_NO_OP_SPAN = _NoOpSpan()


def is_enabled(settings: Settings | None = None) -> bool:
    """Whether telemetry is turned on (``KORCH_TELEMETRY_ENABLED``, default off).

    Args:
        settings: The resolved ``Settings`` for the current call (a composition root already
            holding one, e.g. from ``run_graph``, should pass it). Falls back to the process-wide
            ``get_settings()`` when omitted — correct for the zero-config, unwired case.
    """
    return (settings if settings is not None else get_settings()).korch_telemetry_enabled


def start_span(
    name: str, *, settings: Settings | None = None, **attributes: AttributeValue
) -> AbstractContextManager[Span]:
    """Start a span named ``name`` (spec 08 §4's GenAI span tree, e.g. ``"agent.run"``).

    Returns the module-level no-op singleton when telemetry is disabled, so instrumenting a hot
    code path costs nothing by default.

    Args:
        name: The span name, following the documented GenAI span tree.
        settings: The resolved ``Settings`` for this call; see :func:`is_enabled`.
        attributes: Span attributes. MUST NOT carry prompts, completions, tool arguments, or
            personal data (spec 08 §4/§5 — telemetry follows the same redaction rules as logging).

    Returns:
        A context manager yielding the started :class:`Span` (or the no-op singleton).

    Raises:
        MissingExtraError: If telemetry is enabled but the ``[otel]`` extra is not installed.

    Example:
        >>> from korchestrator.telemetry import start_span
        >>> with start_span("agent.run", run_id="r1") as span:
        ...     span.set_attribute("status", "completed")
    """
    if not is_enabled(settings):
        return _NO_OP_SPAN
    tracer = _tracer()
    # opentelemetry.trace.Tracer.start_as_current_span is typed Iterator[Span] (it is implemented
    # with @contextmanager) but is documented and used as a context manager; the cast reconciles
    # the two.
    return cast(
        "AbstractContextManager[Span]", tracer.start_as_current_span(name, attributes=attributes)
    )


def record_metric(
    name: str, value: float, *, settings: Settings | None = None, **attributes: AttributeValue
) -> None:
    """Record one observation for a named metric (spec 08 §4's six named metrics).

    A no-op when telemetry is disabled.

    Args:
        name: One of the documented metric names, e.g. ``"korch.tool.calls"``.
        value: The observation (a duration in milliseconds, a count, or a delta).
        settings: The resolved ``Settings`` for this call; see :func:`is_enabled`.
        attributes: Metric attributes. MUST be low-cardinality — never ``run_id``.

    Raises:
        MissingExtraError: If telemetry is enabled but the ``[otel]`` extra is not installed.

    Example:
        >>> from korchestrator.telemetry import record_metric
        >>> record_metric("korch.tool.calls", 1, tool="grep", ok=True)
    """
    if not is_enabled(settings):
        return
    kind = _METRIC_KINDS.get(name, "counter")
    instrument = _instrument(name, kind)
    if kind == "histogram":
        cast("Histogram", instrument).record(value, attributes=attributes)
    else:
        cast("Counter | UpDownCounter", instrument).add(value, attributes=attributes)


def _otel() -> tuple[ModuleType, ModuleType]:
    """Lazily import the OTel API, wrapping a missing ``[otel]`` extra actionably."""
    try:
        import opentelemetry.metrics as otel_metrics
        import opentelemetry.trace as otel_trace
    except ImportError as exc:
        raise MissingExtraError(
            "KORCH_TELEMETRY_ENABLED is set but the 'otel' extra is not installed. "
            "Install it with: pip install 'korchestrator[otel]'"
        ) from exc
    return otel_trace, otel_metrics


def _tracer() -> Tracer:
    otel_trace, _ = _otel()
    tracer: Tracer = otel_trace.get_tracer("korchestrator")
    return tracer


def _instrument(name: str, kind: str) -> object:
    if name not in _INSTRUMENTS:
        _, otel_metrics = _otel()
        meter = otel_metrics.get_meter("korchestrator")
        if kind == "histogram":
            _INSTRUMENTS[name] = meter.create_histogram(name)
        elif kind == "up_down_counter":
            _INSTRUMENTS[name] = meter.create_up_down_counter(name)
        else:
            _INSTRUMENTS[name] = meter.create_counter(name)
    return _INSTRUMENTS[name]
