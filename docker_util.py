import re
import logging

from subprocess import check_output, CalledProcessError
from aci_compute_worker import _send_update


def docker_image_clean(image_name):
    # Remove all excess whitespaces on edges, split on spaces and grab the first word.
    # Wraps in double quotes so bash cannot interpret as an exec
    image_name = '"{}"'.format(image_name.strip().split(' ')[0])
    # Regex acts as a whitelist here. Only alphanumerics and the following symbols are allowed: / . : -.
    # If any not allowed are found, replaced with second argument to sub.
    image_name = re.sub('[^0-9a-zA-Z/.:-]+', '', image_name)
    return image_name


def do_docker_pull(image_name, task_id, secret):
    logging.info("Running docker pull for image: {}".format(image_name))
    try:
        cmd = ['docker', 'pull', image_name]
        docker_pull = check_output(cmd)
        logging.info("Docker pull complete for image: {0} with output of {1}".format(
            image_name, docker_pull))
    except CalledProcessError as error:
        logging.info("Docker pull for image: {} returned a non-zero exit code!")

        _send_update(task_id, 'failed', secret, extra={
            'traceback': error.output,
            'metadata': error.returncode
        })
