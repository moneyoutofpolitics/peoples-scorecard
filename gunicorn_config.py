# Gunicorn configuration file for The People's Scorecard
# This file configures Gunicorn settings for better performance

import multiprocessing

# Server socket
bind = "0.0.0.0:10000"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Timeout settings
timeout = 180  # Increased to 180 seconds (3 minutes) to handle large FEC datasets
graceful_timeout = 180
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "peoples-scorecard"

# Server mechanics
daemon = False
pidfile = None
