import os

# Gunicorn configuration file
bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = int(os.environ.get("WEB_CONCURRENCY", 3))
timeout = 120
accesslog = "-"
errorlog = "-"
