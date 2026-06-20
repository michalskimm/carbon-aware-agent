"""OpenTelemetry tracing for the carbon-aware agent service."""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def configure_observability() -> None:
    """Set up the OTel tracer. Call once at startup."""
    provider = TracerProvider(resource=Resource.create({"service.name": "carbon-aware-agent"}))
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):  # real backend if configured
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


tracer = trace.get_tracer("carbon-aware-agent")
