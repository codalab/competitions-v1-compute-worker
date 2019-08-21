import os


broker_url = os.environ.get('BROKER_URL')
broker_use_ssl = os.environ.get('BROKER_USE_SSL', False)
imports = ('worker',)
task_serializer = 'json'
accept_content = ('json',)
worker_max_tasks_per_child = 1
worker_prefetch_multiplier = 1
