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
    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=f"redis://{redis_client.connection_pool.connection_kwargs.get('host')}:{redis_client.connection_pool.connection_kwargs.get('port')}",
        storage_options={"password": redis_client.connection_pool.connection_kwargs.get('password')},
        default_limits=["100 per minute", "10 per second"]
    )

    # Decorate all routes with the rate limiter
    limiter.limit("100/minute;10/second")(app.router)

    @app.route('/', methods=['GET'])
    def get_counter():
        # ... (route logic remains the same)
        pass

    @app.route('/', methods=['POST'])
    def increment_counter():
        # ... (route logic remains the same)
        pass

    @app.route('/health', methods=['GET'])
    @limiter.exempt
    def health_check():
        # ... (route logic remains the same)
        pass

    @app.route('/metrics', methods=['GET'])
    @limiter.exempt
    def metrics_endpoint():
        # ... (route logic remains the same)
        pass

    # ... (error handlers remain the same)
    
    return app
