"""
Gunicorn configuration file.
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'counter-service'

# Proxy configuration
# Trust the X-Forwarded-For header from our Envoy proxy.
# '*' is a security risk in production if not properly firewalled,
# but is acceptable here as traffic should only come from the Envoy proxy within the cluster.
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None


def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting counter-service")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Counter-service is ready. Spawning workers")

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    """Called when a worker times out."""
    worker.log.warning("Worker timeout (pid: %s)", worker.pid)
