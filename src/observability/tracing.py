"""Optional OpenTelemetry setup; safe no-op when cloud tracing is not requested."""
import os
from contextlib import contextmanager
from uuid import uuid4


def trace_id_for_current_span() -> str:
    """Return the active OpenTelemetry trace ID or a request correlation ID."""
    try:
        from opentelemetry import trace
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            return f"{context.trace_id:032x}"
    except ImportError:
        pass
    return uuid4().hex


@contextmanager
def request_span(service: str, alert_id: str):
    """Create a request span and expose its real trace ID when an SDK is configured."""
    try:
        from opentelemetry import trace
    except ImportError:
        yield uuid4().hex
        return
    tracer = trace.get_tracer("sentinelops.api")
    with tracer.start_as_current_span("sentinelops.triage") as span:
        span.set_attribute("sentinelops.service", service)
        span.set_attribute("sentinelops.alert_id", alert_id)
        context = span.get_span_context()
        yield f"{context.trace_id:032x}" if context.is_valid else uuid4().hex


def configure_tracing() -> bool:
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": "sentinelops"}))
    provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
    trace.set_tracer_provider(provider)
    return True
