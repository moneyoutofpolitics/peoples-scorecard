# Gunicorn configuration file for The People's Scorecard
# This file configures Gunicorn settings for better performance

import multiprocessing

# Server socket
bind = "0.0.0.0:10000"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Timeout settings
timeout = 120  # Increased to 120 seconds (2 minutes) to handle FEC API requests
graceful_timeout = 120
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
