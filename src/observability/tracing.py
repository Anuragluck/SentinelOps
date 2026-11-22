"""Optional OpenTelemetry setup; safe no-op when cloud tracing is not requested."""
import os


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
