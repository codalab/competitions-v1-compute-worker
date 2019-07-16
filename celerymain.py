import logging
import os
from celery import Celery

class CeleryWorker():

    def __init__(self, *args, **kwargs):
        self.app = Celery(*args, **kwargs)
        self.app.config_from_object('celeryconfig')
        # main_host_app = Celery('aci_compute_worker', broker=os.environ.get('MAIN_BROKER_URL'))

    def _send_update(self, task_id, status, secret, virtual_host='/', extra=None):
        """
        Sends a status update about the running task.

        id: The task ID.
        status: The new status for the task. One of 'running', 'finished' or 'failed'.
        """
        task_args = {'status': status}
        if extra:
            task_args['extra'] = extra
        logging.info("Updating task=%s status to %s", task_id, status)
        with self.app.connection() as new_connection:
            # We need to send on the main virtual host, not whatever host we're currently
            # connected to.
            new_connection.virtual_host = virtual_host
            new_connection.userid = os.getenv("MAIN_BROKER_LOGIN", "guest")
            new_connection.password = os.getenv("MAIN_BROKER_PASS", "guest")
            self.app.send_task(
                'apps.web.tasks.update_submission',
                args=(task_id, task_args, secret),
                connection=new_connection,
                queue="submission-updates",
            )


worker = CeleryWorker('aci_compute_worker')
app = worker.app