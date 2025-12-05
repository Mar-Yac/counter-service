"""
OpenTelemetry configuration for unified observability.
"""

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.resources import Resource

# Global variables for Prometheus reader
_prometheus_reader = None


def setup_opentelemetry():
    """
    Configure OpenTelemetry for traces and metrics.
    Returns the meter, tracer, and prometheus_reader instances.
    """
    # Create resource with service information
    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "counter-service"),
        "service.version": os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
        "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "prod"),
        "deployment.environment": os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", "production"),
    })
    
    # Setup Tracer Provider
    trace_provider = TracerProvider(resource=resource)
    
    # Add OTLP exporter for traces (if OTLP endpoint is configured)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{otlp_endpoint}/v1/traces",
            headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS", ""),
        )
        trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    else:
        # Use console exporter for development/debugging
        console_exporter = ConsoleSpanExporter()
        trace_provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(__name__)
    
    # Setup Meter Provider with Prometheus exporter
    global _prometheus_reader
    _prometheus_reader = PrometheusMetricReader()
    metrics_provider = MeterProvider(
        resource=resource,
        metric_readers=[_prometheus_reader],
    )
    metrics.set_meter_provider(metrics_provider)
    meter = metrics.get_meter(__name__)
    
    return tracer, meter, _prometheus_reader


def get_otel_metrics(meter):
    """
    Create OpenTelemetry metrics instruments.
    """
    # HTTP request counter
    http_requests = meter.create_counter(
        name="http_requests_total",
        description="Total number of HTTP requests",
        unit="1",
    )
    
    # HTTP request duration histogram
    http_request_duration = meter.create_histogram(
        name="http_request_duration_seconds",
        description="HTTP request duration in seconds",
        unit="s",
    )
    
    # Counter value gauge
    counter_gauge = meter.create_up_down_counter(
        name="counter_value",
        description="Current counter value",
        unit="1",
    )
    
    # Redis connection status gauge
    redis_status = meter.create_up_down_counter(
        name="redis_connection_status",
        description="Redis connection status (1=connected, 0=disconnected)",
        unit="1",
    )
    
    # Redis operation counter
    redis_operations = meter.create_counter(
        name="redis_operations_total",
        description="Total number of Redis operations",
        unit="1",
    )
    
    # Redis operation duration histogram
    redis_duration = meter.create_histogram(
        name="redis_operation_duration_seconds",
        description="Redis operation duration in seconds",
        unit="s",
    )
    
    return {
        "http_requests": http_requests,
        "http_request_duration": http_request_duration,
        "counter_value": counter_gauge,
        "redis_status": redis_status,
        "redis_operations": redis_operations,
        "redis_duration": redis_duration,
    }
