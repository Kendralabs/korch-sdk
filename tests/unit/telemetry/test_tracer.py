"""Telemetry mechanism tests (spec 08 §4, P8.7): zero overhead off, real spans/metrics on."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from unittest import mock

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from korchestrator import MissingExtraError
from korchestrator.config import configure
from korchestrator.telemetry import is_enabled, record_metric, start_span
from korchestrator.telemetry.tracer import _INSTRUMENTS, _NO_OP_SPAN


@pytest.fixture(autouse=True)
def _clear_instrument_cache() -> Iterator[None]:
    # _INSTRUMENTS is a module-level cache keyed by metric name; each test below binds its own
    # in-memory provider, so a name cached from an earlier test would silently skip that binding.
    _INSTRUMENTS.clear()
    yield
    _INSTRUMENTS.clear()


# --- is_enabled -----------------------------------------------------------------------------------


def test_is_enabled_defaults_to_false(settings: None) -> None:
    configure(dotenv_path=None)
    assert is_enabled() is False


def test_is_enabled_reflects_settings(settings: None) -> None:
    configure(dotenv_path=None, korch_telemetry_enabled=True)
    assert is_enabled() is True


# --- disabled: zero overhead ------------------------------------------------------------------


def test_start_span_disabled_returns_the_same_singleton_every_call(settings: None) -> None:
    configure(dotenv_path=None)
    first = start_span("agent.run", run_id="r1")
    second = start_span("agent.plan", agent_id="a1")
    assert first is second is _NO_OP_SPAN


def test_start_span_disabled_works_as_a_context_manager(settings: None) -> None:
    configure(dotenv_path=None)
    with start_span("agent.run") as span:
        span.set_attribute("status", "completed")  # no-op; must not raise


def test_record_metric_disabled_is_a_no_op(settings: None) -> None:
    configure(dotenv_path=None)
    record_metric("korch.tool.calls", 1, tool="grep")  # must not raise or import otel
    assert "korch.tool.calls" not in _INSTRUMENTS


# --- enabled without the [otel] extra -----------------------------------------------------------


def test_start_span_enabled_without_otel_raises_missing_extra(settings: None) -> None:
    configure(dotenv_path=None, korch_telemetry_enabled=True)
    with (
        mock.patch.dict(sys.modules, {"opentelemetry": None, "opentelemetry.trace": None}),
        pytest.raises(MissingExtraError),
    ):
        start_span("agent.run")


def test_record_metric_enabled_without_otel_raises_missing_extra(settings: None) -> None:
    configure(dotenv_path=None, korch_telemetry_enabled=True)
    with (
        mock.patch.dict(sys.modules, {"opentelemetry": None, "opentelemetry.metrics": None}),
        pytest.raises(MissingExtraError),
    ):
        record_metric("korch.tool.calls", 1)


# --- enabled with a real (in-memory) OTel backend -----------------------------------------------


def test_start_span_enabled_emits_a_real_span_with_attributes(
    settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(dotenv_path=None, korch_telemetry_enabled=True)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("opentelemetry.trace.get_tracer", lambda name: provider.get_tracer(name))

    with start_span("agent.run", run_id="r1", tenant_id="default") as span:
        span.set_attribute("status", "completed")

    (recorded,) = exporter.get_finished_spans()
    assert recorded.name == "agent.run"
    assert recorded.attributes is not None
    assert recorded.attributes["run_id"] == "r1"
    assert recorded.attributes["tenant_id"] == "default"
    assert recorded.attributes["status"] == "completed"


def test_start_span_enabled_never_carries_a_prompt_shaped_attribute(
    settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression guard for the boundary rule (spec 08 §4/§5): callers pass whatever attributes
    # they choose, so this asserts the mechanism itself doesn't add anything beyond what's given.
    configure(dotenv_path=None, korch_telemetry_enabled=True)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("opentelemetry.trace.get_tracer", lambda name: provider.get_tracer(name))

    with start_span("agent.plan", agent_id="a1"):
        pass

    (recorded,) = exporter.get_finished_spans()
    assert recorded.attributes is not None
    assert set(recorded.attributes) == {"agent_id"}


def test_record_metric_enabled_records_a_histogram_observation(
    settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(dotenv_path=None, korch_telemetry_enabled=True)
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    monkeypatch.setattr("opentelemetry.metrics.get_meter", lambda name: provider.get_meter(name))

    record_metric("korch.run.duration", 12.5, status="completed")

    (point,) = _data_points(reader, "korch.run.duration")
    assert point.sum == 12.5


def test_record_metric_enabled_records_a_counter_and_an_up_down_counter(
    settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(dotenv_path=None, korch_telemetry_enabled=True)
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    monkeypatch.setattr("opentelemetry.metrics.get_meter", lambda name: provider.get_meter(name))

    record_metric("korch.tool.calls", 1, tool="grep")
    record_metric("korch.agents.active", -1)

    (calls,) = _data_points(reader, "korch.tool.calls")
    (active,) = _data_points(reader, "korch.agents.active")
    assert calls.value == 1
    assert active.value == -1


def _data_points(reader: InMemoryMetricReader, metric_name: str) -> tuple[object, ...]:
    data = reader.get_metrics_data()
    assert data is not None
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == metric_name:
                    return tuple(metric.data.data_points)
    raise AssertionError(f"no data points recorded for {metric_name!r}")
