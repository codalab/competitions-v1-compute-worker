import os


BROKER_URL = os.environ.get('BROKER_URL')
CELERY_IMPORTS = ('worker',)
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ('json',)
