from multiprocessing import cpu_count

# Server Socket
bind = '127.0.0.1:9001'
# bind = 'unix:/home/intioptima/backend-sosmed/gunicorn.sock'

# Worker Options
workers = cpu_count() + 1
worker_class = 'uvicorn.workers.UvicornWorker'

# Logging Options
loglevel = 'debug'  # Log level
accesslog = '/home/intioptima/backend-sosmed/logs/access.log'
errorlog = '/home/intioptima/backend-sosmed/logs/error.log'
