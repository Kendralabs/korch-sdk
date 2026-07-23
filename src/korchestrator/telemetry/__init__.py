"""Leaf-utility layer.

Allowed imports (beyond stdlib + pydantic): config, models; OpenTelemetry packages lazy ([otel]
extra). Emits optional OpenTelemetry spans and metrics with zero cost when disabled.
"""

from korchestrator.telemetry.tracer import Span, is_enabled, record_metric, start_span

__all__ = ["Span", "is_enabled", "record_metric", "start_span"]
