#!/usr/bin/env python
import json
import os
import uuid
import psutil
import socket
import time
import traceback
import yaml
import shutil
import tempfile

from cloudhunky.aci_worker import ACIWorker
from cloudhunky.util import get_afs_creds
from . import util, docker_util, codalabworker_logger


# Config Azure ACI worker
resource_group_name = "ACI"
aci_worker = ACIWorker(resource_group_name)
afs_creds = get_afs_creds()
afs_name = afs_creds["AFS_NAME"]
afs_key = afs_creds["AFS_KEY"]
afs_share = os.getenv("AFS_SHARE")
steps = os.getenv("STEPS","/tmp/codalab/steps")


def aci_run(worker, task_id, task_args):
    """
    Performs a Run.

    task_id: The tracking ID for this task.
    task_args: The input arguments for this task:
    """
    steps_dir=steps+'/'+task_id
    if not os.path.exists(steps_dir):
        os.makedirs(steps_dir)
    codalabworker_logger.info("Entering run task; task_id=%s, task_args=%s", task_id, task_args)
    docker_image = docker_util.docker_image_clean(task_args['docker_image'])
    bundle_url = task_args['bundle_url']
    ingestion_program_docker_image = docker_util.docker_image_clean(
        task_args['ingestion_program_docker_image'])
    output_url = task_args['output_url']
    private_output_url = task_args['private_output_url']

    execution_time_limit = task_args['execution_time_limit']
    is_predict_step = task_args.get("predict", False)
    is_scoring_step = not is_predict_step
    secret = task_args['secret']
    temp_dir = os.environ.get('SUBMISSION_TEMP_DIR', '/tmp/codalab')
    mounted_dir = os.environ.get('SUBMISSION_TEMP_DIR', '/tmp/codalab')
    root_dir = None

    if is_predict_step:
        codalabworker_logger.info("Task is prediction.")
    else:
        codalabworker_logger.info("Task is scoring.")

    running_processes = '<DISABLED>'
    debug_metadata = {
        "hostname": os.environ.get("CODALAB_HOSTNAME") or socket.gethostname(),

        "ingestion_program_duration": None,

        "processes_running_in_temp_dir": running_processes,

        "beginning_virtual_memory_usage": json.dumps(
            psutil.virtual_memory()._asdict()),
        "beginning_swap_memory_usage": json.dumps(psutil.swap_memory()._asdict()),
        "beginning_cpu_usage": psutil.cpu_percent(interval=None),

        "end_virtual_memory_usage": None,
        "end_swap_memory_usage": None,
        "end_cpu_usage": None,
    }

    try:
        worker._send_update(task_id, 'running', secret, extra={
            'metadata': debug_metadata
        })

        # Create temporary directories for the run
        root_dir = tempfile.mkdtemp(dir=temp_dir)
        os.chmod(root_dir, 0o777)
        run_dir = os.path.join(root_dir, 'run')
        shared_dir = tempfile.mkdtemp(dir=temp_dir)
        hidden_ref_dir = ''

        # Fetch and stage the bundles
        start = time.time()
        codalabworker_logger.info("Fetching bundles...")
        bundles = util.get_bundle(root_dir, 'run', bundle_url)
        # If we were passed hidden data, move it
        if is_predict_step:
            hidden_ref_original_location = os.path.join(run_dir, 'hidden_ref')
            if os.path.exists(hidden_ref_original_location):
                codalabworker_logger.info(
                    "Found reference data AND an ingestion program, hiding reference data for ingestion program to use.")
                shutil.move(hidden_ref_original_location, temp_dir)
                hidden_ref_dir = os.path.join(temp_dir, 'hidden_ref')

        codalabworker_logger.info("Metadata: %s" % bundles)
        end = time.time() - start
        codalabworker_logger.info("Fetched bundles in %s", end)

        # Verify we have an input folder: create one if it's not in the bundle.
        input_rel_path = 'input'
        input_dir = os.path.join(root_dir, 'run', 'input')
        if input_rel_path not in bundles:
            if os.path.exists(input_dir) == False:
                os.mkdir(input_dir)
                os.chmod(input_dir, 0o777)

        # Verify we have a program
        prog_rel_path = 'program'
        if prog_rel_path not in bundles:
            raise Exception("Program bundle is not available.")
        ingestion_prog_info = None
        if 'ingestion_program' in bundles:
            ingestion_prog_info = bundles['ingestion_program']
            if not ingestion_prog_info:
                raise Exception(
                    "Ingestion program is missing metadata. Make sure the folder structure is "
                    "appropriate (metadata not in a subdirectory).")
        codalabworker_logger.info("Ingestion program: {}".format(ingestion_prog_info))

        # Look for submission/scoring program metadata, if we're scoring -- otherwise ingestion
        # program will handle the case where a code submission has no metadata.
        prog_info = bundles[prog_rel_path] or {}
        if prog_info is None and is_scoring_step:
            raise Exception("Program metadata is not available.")
        prog_cmd_list = []
        if 'command' in prog_info:
            if isinstance(prog_info['command'], type([])):
                prog_cmd_list = [_.strip() for _ in prog_info['command']]
            else:
                prog_cmd_list = [prog_info['command'].strip()]
        if len(prog_cmd_list) <= 0 and is_scoring_step:
            raise Exception("Program command is not specified.")

        # Create output folder
        output_dir = os.path.join(root_dir, 'run', 'output')
        if os.path.exists(output_dir) == False:
            os.mkdir(output_dir)
            os.chmod(output_dir, 0o777)
        # Create temp folder
        temp_dir = os.path.join(root_dir, 'run', 'temp')
        if os.path.exists(temp_dir) == False:
            os.mkdir(temp_dir)
            os.chmod(temp_dir, 0o777)
        # Report the list of folders and files staged
        #
        # Invoke custom evaluation program
        os.chdir(run_dir)
        os.environ["PATH"] += os.path.sep + run_dir + "/program"
        codalabworker_logger.info("Execution directory: %s", run_dir)
        prog_status = []
        run_ingestion_program = False
        timed_out = False
        exit_code = None
        ingestion_program_exit_code = None

        # If our program command list is empty and we're not scoring, we probably got a result submission
        if not prog_cmd_list and is_predict_step:
            prog_cmd_list = ['']

        for prog_cmd_counter, prog_cmd in enumerate(prog_cmd_list):
            startTime = time.time()

            # Ingestion programs (optional) determine whether or not a submission is code or results, and then
            # if given, run the code or move the results appropriately
            if is_predict_step:
                codalabworker_logger.info("Doing ingestion program checks")

                # Check that we should even be running this submission in a special way, may
                # just be results..
                submission_path = os.path.join(run_dir, "program")
                metadata_path = os.path.join(submission_path, "metadata")

                # If a metadata file is found, assume this is a code submission
                is_code_submission = os.path.exists(metadata_path)
                # if exists(metadata_path):
                #     submission_metadata = yaml.load(open(metadata_path).read())
                #     is_code_submission = "command" in submission_metadata.keys()

                if is_code_submission:
                    codalabworker_logger.info("We have a code submission!")

                # We're in prediction so use an ingestion program to process the submission.
                # Was an ingestion program provided?
                if is_code_submission and ingestion_prog_info:
                    codalabworker_logger.info(
                        "Running organizer provided ingestion program and submission.")
                    # Run ingestion program, run submission
                    run_ingestion_program = True
                elif is_code_submission:
                    codalabworker_logger.info(
                        "Running code submission like normal, no ingestion program provided.")
                else:
                    # We didn't find an ingestion program, let's use the following simple one
                    # that just executes the submission and moves results
                    codalabworker_logger.info(
                        "No code submission, moving input directory to output.")
                    # This isn't a code submission, it is already ready to score. Remove
                    # old output directory and replace it with this submission's contents.
                    codalabworker_logger.info("Removing output_dir: {}".format(output_dir))
                    os.rmdir(output_dir)
                    codalabworker_logger.info(
                        "Renaming submission_path: {} to old output_dir name {}".format(
                            submission_path, output_dir))
                    os.rename(submission_path, output_dir)
            else:
                # During scoring we don't worry about sharing directories and such when using ingestion programs
                if ingestion_prog_info:
                    codalabworker_logger.info(
                        "Running organizer provided ingestion program for scoring")
                    run_ingestion_program = True

            if prog_cmd:
                # Update command-line with the real paths
                prog_cmd = prog_cmd \
                    .replace("$program", os.path.join(run_dir, 'program')) \
                    .replace("$predictions", os.path.join(run_dir, 'input', 'res')) \
                    .replace("$input", os.path.join(run_dir, 'input')) \
                    .replace("$output", os.path.join(run_dir, 'output')) \
                    .replace("$tmp", os.path.join(run_dir, 'temp')) \
                    .replace("$shared", shared_dir) \
                    .replace("/", os.path.sep) \
                    .replace("\\", os.path.sep)

                envs = {'PYTHONUNBUFFERED': 1, 'STEPS' : steps_dir}
                # TODO: add dynamic resource params
                prog_cmd = ["/bin/bash", "-c", f"cd {run_dir} && (time {prog_cmd}) |& tee {os.path.join(output_dir, 'output.txt')}"]
                codalabworker_logger.info("Invoking ACI container with cmd: %s",
                             " ".join(prog_cmd))

                cpu, memory_in_gb, gpu_count = util.get_resources(task_args)
                codalabworker_logger.info(f"Invoking ACI container with CPU {cpu}, RAM {memory_in_gb}, GPU {gpu_count}")
                aci_worker.run_task_based_container(
                    container_image_name=docker_image,
                    command=prog_cmd,
                    # command=["/bin/bash", "-c", "sleep 1000000"],
                    cpu=cpu,
                    memory_in_gb=memory_in_gb,
                    gpu_count=gpu_count,
                    envs=envs,
                    volume_mount_path=mounted_dir,
                    timeout=execution_time_limit,
                    afs_name=afs_name,
                    afs_key=afs_key,
                    afs_share=afs_share,
                    afs_mount_subpath='')
            # TODO: Test ingestion !
            if run_ingestion_program:
                if 'command' not in ingestion_prog_info:
                    raise Exception(
                        "Ingestion program metadata was found, but is missing the 'command' attribute,"
                        "which is necessary to execute the ingestion program.")

                ingestion_prog_cmd = ingestion_prog_info['command']
                ingestion_prog_cmd = ingestion_prog_cmd \
                    .replace("$program", os.path.join(run_dir, 'ingestion_program')) \
                    .replace("$ingestion_program",
                             os.path.join(run_dir, 'ingestion_program')) \
                    .replace("$submission_program", os.path.join(run_dir, 'program')) \
                    .replace("$predictions", os.path.join(run_dir, 'input', 'res')) \
                    .replace("$input", os.path.join(run_dir, 'input')) \
                    .replace("$output", os.path.join(run_dir, 'output')) \
                    .replace("$tmp", os.path.join(run_dir, 'temp')) \
                    .replace("$shared", shared_dir) \
                    .replace("$hidden", hidden_ref_dir) \
                    .replace("/", os.path.sep) \
                    .replace("\\", os.path.sep)

                codalabworker_logger.error(ingestion_prog_cmd)
                # TODO: rewrite according to prediction stage
                ingestion_prog_cmd = ["/bin/bash", "-c",
                                      f"cd {run_dir} && " + prog_cmd + " |& tee output.txt"]
                codalabworker_logger.info("Invoking ingestion program: %s",
                             " ".join(ingestion_prog_cmd))
                aci_worker.run_task_based_container(
                    container_image_name=ingestion_program_docker_image,
                    command=ingestion_prog_cmd,
                    cpu=2.0,
                    memory_in_gb=16,
                    gpu_count=gpu_count,
                    envs=envs,
                    volume_mount_path=mounted_dir,
                    afs_name=afs_name,
                    afs_key=afs_key,
                    afs_share=afs_share,
                    afs_mount_subpath='')

            exit_code = 0
            ingestion_program_exit_code = 0
            endTime = time.time()
            elapsedTime = endTime - startTime

            if len(prog_cmd_list) == 1:
                # Overwrite prog_status array with dict
                prog_status = {
                    'exitCode': exit_code,
                    'ingestionExitCode': ingestion_program_exit_code,
                    'elapsedTime': elapsedTime
                }
            else:
                # otherwise we're doing multi-track and processing multiple commands so append to the array
                prog_status.append({
                    'exitCode': exit_code,
                    'ingestionExitCode': ingestion_program_exit_code,
                    'elapsedTime': elapsedTime
                })
            with open(os.path.join(output_dir, 'metadata'), 'a+') as f:
                f.write(yaml.dump(prog_status, default_flow_style=False))

            if timed_out or exit_code != 0 or ingestion_program_exit_code != 0:
                # Submission failed somewhere in here, bomb out
                break
        private_dir = os.path.join(output_dir, 'private')
        if os.path.exists(private_dir):
            codalabworker_logger.info("Packing private results...")
            private_output_file = os.path.join(root_dir, 'run', 'private_output.zip')
            shutil.make_archive(os.path.splitext(private_output_file)[0], 'zip',
                                output_dir)
            util.put_blob(private_output_url, private_output_file)
            shutil.rmtree(private_dir, ignore_errors=True)

        # Pack results and send them to Blob storage
        codalabworker_logger.info("Packing results...")
        output_file = os.path.join(root_dir, 'run', 'output.zip')
        shutil.make_archive(os.path.splitext(output_file)[0], 'zip', output_dir)
        util.put_blob(output_url, output_file)

        debug_metadata["end_virtual_memory_usage"] = json.dumps(
            psutil.virtual_memory()._asdict())
        debug_metadata["end_swap_memory_usage"] = json.dumps(
            psutil.swap_memory()._asdict())
        debug_metadata["end_cpu_usage"] = psutil.cpu_percent(interval=None)

        # check if timed out AFTER output files are written! If we exit sooner, no output is written
        if timed_out:
            codalabworker_logger.exception("Run task timed out (task_id=%s).", task_id)
            worker._send_update(task_id, 'failed', secret, extra={
                'metadata': debug_metadata
            })
        elif exit_code != 0 or ingestion_program_exit_code != 0:
            codalabworker_logger.exception("Run task exit code non-zero (task_id=%s).", task_id)
            worker._send_update(task_id, 'failed', secret, extra={
                'traceback': None,
                'metadata': debug_metadata
            })
        else:
            worker._send_update(task_id, 'finished', secret, extra={
                'metadata': debug_metadata
            })
    except Exception:
        if debug_metadata['end_virtual_memory_usage'] == None:
            # We didnt' make it far enough to save end metadata... so do it!
            debug_metadata["end_virtual_memory_usage"] = json.dumps(
                psutil.virtual_memory()._asdict())
            debug_metadata["end_swap_memory_usage"] = json.dumps(
                psutil.swap_memory()._asdict())
            debug_metadata["end_cpu_usage"] = psutil.cpu_percent(interval=None)

        codalabworker_logger.exception("Run task failed (task_id=%s).", task_id)
        worker._send_update(task_id, 'failed', secret, extra={
            'traceback': traceback.format_exc(),
            'metadata': debug_metadata
        })

    if root_dir is not None and not os.environ.get("DONT_FINALIZE_SUBMISSION"):
        try:
            shutil.rmtree(root_dir, ignore_errors=True)
            codalabworker_logger.info(f"{root_dir} was cleaned")
        except:
            codalabworker_logger.exception("Unable to clean-up local folder %s (task_id=%s)",
                              root_dir, task_id)
