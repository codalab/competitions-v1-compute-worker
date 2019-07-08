import os


BROKER_URL = os.environ.get('BROKER_URL')
MAIN_BROKER_URL = os.environ.get('MAIN_BROKER_URL')
BROKER_USE_SSL = os.environ.get('BROKER_USE_SSL', False)
CELERY_IMPORTS = ('aci_compute_worker',)
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ('json',)
