"""
Flask application for the counter service with OpenTelemetry and Rate Limiting.
"""

import os
import logging
import time

from flask import Flask, jsonify, request
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pythonjsonlogger import jsonlogger
import redis
from redis.exceptions import ConnectionError as RedisConnectionError

from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry import trace

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config.otel_config import setup_opentelemetry, get_otel_metrics

# Initialize OpenTelemetry
tracer, meter, prometheus_reader = setup_opentelemetry()
otel_metrics = get_otel_metrics(meter)


def setup_logging():
    """Configure structured JSON logging."""
    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    log_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)
    
    return logger


def create_redis_client():
    """Create and return a Redis client, reading password from a file if specified."""
    host = os.getenv('REDIS_HOST', 'counter-redis-master')
    port = int(os.getenv('REDIS_PORT', 6379))
    db = int(os.getenv('REDIS_DB', 0))
    password = None
    
    password_file = os.getenv('REDIS_PASSWORD_FILE')
    if password_file:
        try:
            with open(password_file, 'r') as f:
                password = f.read().strip()
        except IOError as e:
            logging.getLogger().error(f"Could not read Redis password file: {e}")
    else:
        password = os.getenv('REDIS_PASSWORD') or None

    return redis.Redis(
        host=host,
        port=port,
        password=password,
        db=db,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True
    )


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    logger = setup_logging()
    
    # Instrument Flask with OpenTelemetry
    FlaskInstrumentor().instrument_app(app)
    
    try:
        redis_client = create_redis_client()
        redis_client.ping()
        RedisInstrumentor().instrument()
        otel_metrics["redis_status"].add(1)
        logger.info("Redis connection established")
    except Exception as e:
        logger.error("Failed to connect to Redis", extra={"error": str(e)})
        otel_metrics["redis_status"].add(-1)
        redis_client = None

    # Initialize Rate Limiter
    # The default_limits apply to all routes unless explicitly exempted or overridden.
    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=f"redis://{redis_client.connection_pool.connection_kwargs.get('host')}:{redis_client.connection_pool.connection_kwargs.get('port')}",
        storage_options={"password": redis_client.connection_pool.connection_kwargs.get('password')},
        default_limits=["100 per minute", "10 per second"]
    )

    # The line `limiter.limit("100/minute;10/second")(app.router)` was incorrect and redundant.
    # The default_limits already apply to all routes.

    @app.route('/', methods=['GET'])
    def get_counter():
        """Return the current counter value."""
        start_time = time.time()
        span = tracer.start_span("get_counter")
        
        try:
            if redis_client is None:
                raise RedisConnectionError("Redis not connected")
            
            # Get counter value from Redis with tracing
            with tracer.start_as_current_span("redis_get") as redis_span:
                redis_start = time.time()
                value = redis_client.get('counter') or '0'
                redis_duration = time.time() - redis_start
                count = int(value)
                
                # Record Redis metrics
                otel_metrics["redis_operations"].add(1, {"operation": "get", "status": "success"})
                otel_metrics["redis_duration"].record(redis_duration, {"operation": "get"})
                redis_span.set_attribute("redis.operation", "get")
                redis_span.set_attribute("redis.key", "counter")
                redis_span.set_attribute("counter.value", count)
            
            # Record counter value
            otel_metrics["counter_value"].add(count)
            
            duration = time.time() - start_time
            otel_metrics["http_requests"].add(1, {"method": "GET", "endpoint": "/", "status": "200"})
            otel_metrics["http_request_duration"].record(duration, {"method": "GET", "endpoint": "/"})
            
            span.set_attribute("http.method", "GET")
            span.set_attribute("http.status_code", 200)
            span.set_attribute("counter.value", count)
            
            logger.info("Counter retrieved", extra={
                "method": "GET",
                "path": "/",
                "counter": count,
                "status": 200,
                "trace_id": format(span.get_span_context().trace_id, "032x"),
                "span_id": format(span.get_span_context().span_id, "016x"),
            })
            
            return jsonify({
                "counter": count,
                "message": "Counter retrieved successfully"
            }), 200
            
        except RedisConnectionError as e:
            duration = time.time() - start_time
            otel_metrics["http_requests"].add(1, {"method": "GET", "endpoint": "/", "status": "503"})
            otel_metrics["http_request_duration"].record(duration, {"method": "GET", "endpoint": "/"})
            span.set_attribute("http.status_code", 503)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            logger.error("Redis connection error", extra={
                "method": "GET",
                "path": "/",
                "error": str(e),
                "status": 503,
                "trace_id": format(span.get_span_context().trace_id, "032x"),
            })
            return jsonify({
                "error": "Service temporarily unavailable",
                "message": "Cannot connect to Redis"
            }), 503
            
        except Exception as e:
            duration = time.time() - start_time
            otel_metrics["http_requests"].add(1, {"method": "GET", "endpoint": "/", "status": "500"})
            otel_metrics["http_request_duration"].record(duration, {"method": "GET", "endpoint": "/"})
            span.set_attribute("http.status_code", 500)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            logger.error("Internal server error", extra={
                "method": "GET",
                "path": "/",
                "error": str(e),
                "status": 500,
                "trace_id": format(span.get_span_context().trace_id, "032x"),
            })
            return jsonify({
                "error": "Internal server error",
                "message": str(e)
            }), 500
        finally:
            span.end()
    
    @app.route('/', methods=['POST'])
    def increment_counter():
        """Increment the counter and return the new value."""
        start_time = time.time()
        span = tracer.start_span("increment_counter")
        
        try:
            if redis_client is None:
                raise RedisConnectionError("Redis not connected")
            
            # Increment counter in Redis with tracing
            with tracer.start_as_current_span("redis_incr") as redis_span:
                redis_start = time.time()
                count = redis_client.incr('counter')
                redis_duration = time.time() - redis_start
                
                # Record Redis metrics
                otel_metrics["redis_operations"].add(1, {"operation": "incr", "status": "success"})
                otel_metrics["redis_duration"].record(redis_duration, {"operation": "incr"})
                redis_span.set_attribute("redis.operation", "incr")
                redis_span.set_attribute("redis.key", "counter")
                redis_span.set_attribute("counter.value", count)
            
            # Record counter value
            otel_metrics["counter_value"].add(count)
            
            duration = time.time() - start_time
            otel_metrics["http_requests"].add(1, {"method": "POST", "endpoint": "/", "status": "200"})
            otel_metrics["http_request_duration"].record(duration, {"method": "POST", "endpoint": "/"})
            
            span.set_attribute("http.method", "POST")
            span.set_attribute("http.status_code", 200)
            span.set_attribute("counter.value", count)
            
            logger.info("Counter incremented", extra={
                "method": "POST",
                "path": "/",
                "counter": count,
                "status": 200,
                "trace_id": format(span.get_span_context().trace_id, "032x"),
                "span_id": format(span.get_span_context().span_id, "016x"),
            })
            
            return jsonify({
                "counter": count,
                "message": "Counter incremented successfully"
            }), 200
            
        except RedisConnectionError as e:
            duration = time.time() - start_time
            otel_metrics["http_requests"].add(1, {"method": "POST", "endpoint": "/", "status": "503"})
            otel_metrics["http_request_duration"].record(duration, {"method": "POST", "endpoint": "/"})
            span.set_attribute("http.status_code", 503)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            logger.error("Redis connection error", extra={
                "method": "POST",
                "path": "/",
                "error": str(e),
                "status": 503,
                "trace_id": format(span.get_span_context().trace_id, "032x"),
            })
            return jsonify({
                "error": "Service temporarily unavailable",
                "message": "Cannot connect to Redis"
            }), 503
            
        except Exception as e:
            duration = time.time() - start_time
            otel_metrics["http_requests"].add(1, {"method": "POST", "endpoint": "/", "status": "500"})
            otel_metrics["http_request_duration"].record(duration, {"method": "POST", "endpoint": "/"})
            span.set_attribute("http.status_code", 500)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            logger.error("Internal server error", extra={
                "method": "POST",
                "path": "/",
                "error": str(e),
                "status": 500,
                "trace_id": format(span.get_span_context().trace_id, "032x"),
            })
            return jsonify({
                "error": "Internal server error",
                "message": str(e)
            }), 500
        finally:
            span.end()
    
    @app.route('/health', methods=['GET'])
    @limiter.exempt
    def health_check():
        """Health check endpoint for Kubernetes probes."""
        span = tracer.start_span("health_check")
        try:
            if redis_client is None:
                otel_metrics["redis_status"].add(-1)
                span.set_attribute("health.status", "unhealthy")
                span.set_attribute("redis.status", "disconnected")
                return jsonify({
                    "status": "unhealthy",
                    "redis": "disconnected"
                }), 503
            
            # Test Redis connection
            redis_client.ping()
            otel_metrics["redis_status"].add(1)
            span.set_attribute("health.status", "healthy")
            span.set_attribute("redis.status", "connected")
            
            return jsonify({
                "status": "healthy",
                "redis": "connected"
            }), 200
            
        except Exception as e:
            otel_metrics["redis_status"].add(-1)
            span.set_attribute("health.status", "unhealthy")
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.warning("Health check failed", extra={"error": str(e)})
            return jsonify({
                "status": "unhealthy",
                "redis": "disconnected",
                "error": str(e)
            }), 503
        finally:
            span.end()
    
    @app.route('/metrics', methods=['GET'])
    @limiter.exempt
    def metrics_endpoint():
        """Prometheus metrics endpoint (OpenTelemetry + Prometheus client)."""
        try:
            # OpenTelemetry Prometheus exporter provides metrics via get_metrics_data
            # The PrometheusMetricReader integrates with the prometheus_client's default registry.
            # Calling generate_latest() will automatically collect metrics from all registered
            # collectors, including the one from OpenTelemetry.
            return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
        except Exception as e:
            # Fallback to legacy metrics if OpenTelemetry export fails
            logger.warning("Failed to export OpenTelemetry metrics", extra={"error": str(e)})
            return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        otel_metrics["http_requests"].add(1, {"method": request.method, "endpoint": request.path, "status": "404"})
        return jsonify({
            "error": "Not found",
            "message": f"The endpoint {request.path} does not exist"
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 errors."""
        otel_metrics["http_requests"].add(1, {"method": request.method, "endpoint": request.path, "status": "405"})
        return jsonify({
            "error": "Method not allowed",
            "message": f"Method {request.method} is not allowed for {request.path}"
        }), 405
    
    return app
