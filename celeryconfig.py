import os

from celery.signals import worker_init

BROKER_URL = os.environ.get('BROKER_URL')
BROKER_USE_SSL = os.environ.get('BROKER_USE_SSL', False)
CELERY_IMPORTS = ('worker',)
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ('json',)
CELERYD_FORCE_EXECV = True
# CELERYD_MAX_TASKS_PER_CHILD = 1
CELERYD_PREFETCH_MULTIPLIER = 1
CELERYD_CONCURRENCY = 1



# @worker_init.connect
# def configure_workers(sender=None, conf=None, **kwargs):
#     import logging
#     logger = logging.getLogger()
#     print("INIT configure workers")
#     # Save worker ID or get existing
#     if not os.path.exists('.worker_registration'):
#         print("Saving worker information and registering")
#         import uuid
#         WORKER_ID = str(uuid.uuid4())
#         with open('.worker_registration', 'w') as worker_info:
#             worker_info.write(WORKER_ID)
#     else:
#         WORKER_ID = open('.worker_registration', 'r').read()
#
#     try:
#         import subprocess
#         gpus = str(subprocess.check_output(["nvidia-smi", "-L"])).count('UUID')
#     except:  # nivida-smi not found TODO: Replace with valid exceptions...!
#         gpus = 0
#
#     from worker import register_worker
#     import multiprocessing
#     from worker import get_available_memory
#     import psutil
#     register_worker(
#         WORKER_ID,
#         multiprocessing.cpu_count(),
#         get_available_memory(),
#         psutil.disk_usage('/').total / (1024.0 ** 3),
#         gpus,
#     )
