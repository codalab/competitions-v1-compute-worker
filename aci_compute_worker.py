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
import logging
from subprocess import Popen

from cloudhunky.aci_worker import ACIWorker
from cloudhunky.util import get_afs_creds
import util
import docker_util

# Config Azure ACI worker
resource_group_name = "ACI"
aci_worker = ACIWorker(resource_group_name)
afs_creds = get_afs_creds()
afs_name = afs_creds["AFS_NAME"]
afs_key = afs_creds["AFS_KEY"]
afs_share = afs_creds["AFS_SHARE"]


def aci_run(worker, task_id, task_args):
    """
    Performs a Run.

    task_id: The tracking ID for this task.
    task_args: The input arguments for this task:
    """
    logging.info("Entering run task; task_id=%s, task_args=%s", task_id, task_args)
    # run_id = task_args['bundle_id']
    docker_image = docker_util.docker_image_clean(task_args['docker_image'])
    bundle_url = task_args['bundle_url']
    ingestion_program_docker_image = docker_util.docker_image_clean(
        task_args['ingestion_program_docker_image'])
    stdout_url = task_args['stdout_url']
    stderr_url = task_args['stderr_url']
    ingestion_program_stderr_url = task_args['ingestion_program_stderr_url']
    ingestion_program_output_url = task_args['ingestion_program_output_url']
    output_url = task_args['output_url']
    detailed_results_url = task_args.get('detailed_results_url')
    private_output_url = task_args['private_output_url']

    execution_time_limit = task_args['execution_time_limit']
    # container = task_args['container_name']
    is_predict_step = task_args.get("predict", False)
    is_scoring_step = not is_predict_step
    secret = task_args['secret']
    current_dir = os.getcwd()
    temp_dir = os.environ.get('SUBMISSION_TEMP_DIR', '/tmp/codalab')
    mounted_dir = os.environ.get('SUBMISSION_TEMP_DIR', '/tmp/codalab')
    root_dir = None
    docker_runtime = os.environ.get('DOCKER_RUNTIME', '')

    # do_docker_pull(docker_image, task_id, secret)

    # if not docker_image == ingestion_program_docker_image:
    #     # If the images are the same only do one
    #     do_docker_pull(ingestion_program_docker_image, task_id, secret)

    if is_predict_step:
        logging.info("Task is prediction.")
    else:
        logging.info("Task is scoring.")

    running_processes = '<DISABLED>'
    debug_metadata = {
        "hostname": os.environ.get("CODALAB_HOSTNAME") or socket.gethostname(),

        "ingestion_program_duration": None,

        "processes_running_in_temp_dir": running_processes,

        "beginning_virtual_memory_usage": json.dumps(
            psutil.virtual_memory()._asdict()),
        "beginning_swap_memory_usage": json.dumps(psutil.swap_memory()._asdict()),
        "beginning_cpu_usage": psutil.cpu_percent(interval=None),

        # following are filled in after test ran + process SHOULD have been closed
        "end_virtual_memory_usage": None,
        "end_swap_memory_usage": None,
        "end_cpu_usage": None,
    }

    try:
        # Cleanup dir in case any processes didn't clean up properly
        for the_file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, the_file)
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path, ignore_errors=True)

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
        logging.info("Fetching bundles...")
        bundles = util.get_bundle(root_dir, 'run', bundle_url)
        # If we were passed hidden data, move it
        if is_predict_step:
            hidden_ref_original_location = os.path.join(run_dir, 'hidden_ref')
            if os.path.exists(hidden_ref_original_location):
                logging.info(
                    "Found reference data AND an ingestion program, hiding reference data for ingestion program to use.")
                shutil.move(hidden_ref_original_location, temp_dir)
                hidden_ref_dir = os.path.join(temp_dir, 'hidden_ref')

        logging.info("Metadata: %s" % bundles)
        end = time.time() - start
        logging.info("Fetched bundles in %s", end)

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
        logging.info("Ingestion program: {}".format(ingestion_prog_info))

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
        os.environ["PATH"] += os.pathsep + run_dir + "/program"
        logging.info("Execution directory: %s", run_dir)

        if is_predict_step:
            stdout_file_name = 'prediction_stdout_file.txt'
            stderr_file_name = 'prediction_stderr_file.txt'
        else:
            stdout_file_name = 'stdout.txt'
            stderr_file_name = 'stderr.txt'

        stdout_file = os.path.join(run_dir, stdout_file_name)
        stderr_file = os.path.join(run_dir, stderr_file_name)
        stdout = open(stdout_file, "a+")
        stderr = open(stderr_file, "a+")
        prog_status = []

        ingestion_stdout_file = os.path.join(run_dir, 'ingestion_stdout_file.txt')
        ingestion_stderr_file = os.path.join(run_dir, 'ingestion_stderr_file.txt')
        ingestion_stdout = open(ingestion_stdout_file, "a+")
        ingestion_stderr = open(ingestion_stderr_file, "a+")
        ingestion_program_start_time = None
        ingestion_program_end_time = None

        default_detailed_result_path = os.path.join(output_dir,
                                                    'detailed_results.html')

        run_ingestion_program = False

        timed_out = False
        exit_code = None
        ingestion_program_exit_code = None
        available_memory_mib = 4000  # get_available_memory()
        logging.info("Available memory: {}MB".format(available_memory_mib))

        # If our program command list is empty and we're not scoring, we probably got a result submission
        if not prog_cmd_list and is_predict_step:
            prog_cmd_list = ['']

        for prog_cmd_counter, prog_cmd in enumerate(prog_cmd_list):
            startTime = time.time()

            # Ingestion programs (optional) determine whether or not a submission is code or results, and then
            # if given, run the code or move the results appropriately

            if is_predict_step:
                logging.info("Doing ingestion program checks")

                # Check that we should even be running this submission in a special way, may
                # just be results..
                submission_path = os.path.join(run_dir, "program")
                metadata_path = os.path.join(submission_path, "metadata")

                # If a metadata file is found, assume this is a code submission
                is_code_submission = os._exists(metadata_path)
                # if exists(metadata_path):
                #     submission_metadata = yaml.load(open(metadata_path).read())
                #     is_code_submission = "command" in submission_metadata.keys()

                if is_code_submission:
                    logging.info("We have a code submission!")

                # We're in prediction so use an ingestion program to process the submission.
                # Was an ingestion program provided?
                if is_code_submission and ingestion_prog_info:
                    logging.info(
                        "Running organizer provided ingestion program and submission.")
                    # Run ingestion program, run submission
                    run_ingestion_program = True
                elif is_code_submission:
                    logging.info(
                        "Running code submission like normal, no ingestion program provided.")
                else:
                    # We didn't find an ingestion program, let's use the following simple one
                    # that just executes the submission and moves results
                    logging.info(
                        "No code submission, moving input directory to output.")
                    # This isn't a code submission, it is already ready to score. Remove
                    # old output directory and replace it with this submission's contents.
                    logging.info("Removing output_dir: {}".format(output_dir))
                    os.rmdir(output_dir)
                    logging.info(
                        "Renaming submission_path: {} to old output_dir name {}".format(
                            submission_path, output_dir))
                    os.rename(submission_path, output_dir)
            else:
                # During scoring we don't worry about sharing directories and such when using ingestion programs
                if ingestion_prog_info:
                    logging.info(
                        "Running organizer provided ingestion program for scoring")
                    run_ingestion_program = True

            if detailed_results_url:
                # Create empty detailed results
                open(default_detailed_result_path, 'a').close()
                os.chmod(default_detailed_result_path, 0o777)

            # evaluator_process = None
            # detailed_result_process = None
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
                # prog_cmd = prog_cmd.split(' ')
                eval_container_name = uuid.uuid4()
                # docker_cmd = [
                #     'docker',
                #     'run',
                #     # Remove it after run
                #     '--rm',
                #     # Give it a name we have stored as a variable
                #     '--name={}'.format(eval_container_name),
                #     # Try the new timeout feature
                #     '--stop-timeout={}'.format(execution_time_limit),
                #     # Don't allow subprocesses to raise privileges
                #     '--security-opt=no-new-privileges',
                #     # Set the right volume
                #     '-v', '{0}:{0}'.format(run_dir),
                #     '-v', '{0}:{0}'.format(shared_dir),
                #     # Set aside 512m memory for the host
                #     '--memory', '{}MB'.format(available_memory_mib - 512),
                #     # Don't buffer python output, so we don't lose any
                #     '-e', 'PYTHONUNBUFFERED=1',
                #     # Set current working directory
                #     '-w', run_dir,
                #     # Set container runtime
                #     '--runtime', docker_runtime,
                #     # Note that hidden data dir is excluded here!
                #     # Set the right image
                #     docker_image,
                # ]

                # prog_cmd = docker_cmd + prog_cmd
                envs = {'PYTHONUNBUFFERED': 1}
                # TODO: working dir, stop-timeout
                prog_cmd = ["/bin/bash", "-c", f"cd {run_dir} && " + prog_cmd]
                logging.info("Invoking ACI container with cmd: %s",
                             " ".join(prog_cmd))
                aci_worker.run_task_based_container(
                    container_image_name=docker_image,
                    command=prog_cmd,
                    # command=["/bin/bash", "-c", "sleep 1000000"],
                    cpu=int(os.getenv("CPU", 2)),
                    memory_in_gb=int(os.getenv("RAM", 8)),
                    gpu_count=int(os.getenv("GPU", 0)),
                    envs=envs,
                    volume_mount_path=mounted_dir,
                    timeout=execution_time_limit,
                    afs_name=afs_name,
                    afs_key=afs_key,
                    afs_share=afs_share,
                    afs_mount_subpath='')

                # evaluator_process = Popen(
                #     prog_cmd,
                #     stdout=stdout,
                #     stderr=stderr,
                #     # env=os.environ,
                #     # cwd=join(run_dir, 'program')
                # )

                # We're running a program, not just result submission, so we should keep an eye on detailed results
                if detailed_results_url:
                    detailed_result_watcher_args = [
                        'bash',
                        '/worker/detailed_result_put.sh',
                        str(detailed_results_url),
                        str(default_detailed_result_path)
                    ]
                    logging.info("Detailed results watcher program: %s",
                                 " ".join(detailed_result_watcher_args))
                    detailed_result_process = Popen(detailed_result_watcher_args)

            if run_ingestion_program:
                if 'command' not in ingestion_prog_info:
                    raise Exception(
                        "Ingestion program metadata was found, but is missing the 'command' attribute,"
                        "which is necessary to execute the ingestion program.")
                ingestion_program_start_time = time.time()

                ingestion_prog_cmd = ingestion_prog_info['command']

                # ingestion_run_dir = join(run_dir, 'ingestion')
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
                # ingestion_prog_cmd = ingestion_prog_cmd.split(' ')
                ingestion_container_name = uuid.uuid4()
                # ingestion_docker_cmd = [
                #     'docker',
                #     'run',
                #     # Remove it after run
                #     '--rm',
                #     # Give it a name we have stored as a variable
                #     '--name={}'.format(ingestion_container_name),
                #     # Try the new timeout feature
                #     '--stop-timeout={}'.format(execution_time_limit),
                #     # Don't allow subprocesses to raise privileges
                #     '--security-opt=no-new-privileges',
                #     # Set the right volume
                #     '-v', '{0}:{0}'.format(run_dir),
                #     '-v', '{0}:{0}'.format(shared_dir),
                #     '-v', '{0}:{0}'.format(hidden_ref_dir),
                #     # Set aside 512m memory for the host
                #     '--memory', '{}MB'.format(available_memory_mib - 512),
                #     # Add the participants submission dir to PYTHONPATH
                #     '-e',
                #     'PYTHONPATH=$PYTHONPATH:{}'.format(join(run_dir, 'program')),
                #     '-e', 'PYTHONUNBUFFERED=1',
                #     # Set current working directory to submission dir
                #     '-w', run_dir,
                #     # Set container runtime
                #     '--runtime', docker_runtime,
                #     # Set the right image
                #     ingestion_program_docker_image,
                # ]
                # ingestion_prog_cmd = ingestion_docker_cmd + ingestion_prog_cmd

                logging.error(ingestion_prog_cmd)
                # ingestion_process = Popen(
                #     ingestion_prog_cmd,
                #     stdout=ingestion_stdout,
                #     stderr=ingestion_stderr,
                #     # cwd=join(run_dir, 'ingestion_program')
                # )
                ingestion_prog_cmd = ["/bin/bash", "-c",
                                      f"cd {run_dir} && " + prog_cmd]
                logging.info("Invoking ingestion program: %s",
                             " ".join(ingestion_prog_cmd))
                aci_worker.run_task_based_container(
                    container_image_name=ingestion_program_docker_image,
                    command=ingestion_prog_cmd,
                    cpu=2.0,
                    memory_in_gb=16,
                    gpu_count=1,
                    envs=envs,
                    volume_mount_path=mounted_dir,
                    afs_name=afs_name,
                    afs_key=afs_key,
                    afs_share=afs_share,
                    afs_mount_subpath='')
            else:
                ingestion_process = None

            # if evaluator_process:
            #     logging.info("Started process, pid=%s" % evaluator_process.pid)
            #
            # if evaluator_process or ingestion_process:
            #     # Only if a program is running do these checks, otherwise infinite loop checking nothing!
            #     time_difference = time.time() - startTime
            #     signal.signal(signal.SIGALRM, alarm_handler)
            #     signal.alarm(
            #         int(math.fabs(math.ceil(execution_time_limit - time_difference))))
            #
            #     logging.info("Checking process, exit_code = %s" % exit_code)
            #
            #     try:
            #         # While either program is running and hasn't exited, continue polling
            #         while (evaluator_process and exit_code == None) or (
            #                 ingestion_process and ingestion_program_exit_code == None):
            #             time.sleep(1)
            #
            #             if evaluator_process and exit_code is None:
            #                 exit_code = evaluator_process.poll()
            #
            #             if ingestion_process and ingestion_program_exit_code is None:
            #                 ingestion_program_exit_code = ingestion_process.poll()
            #     except (ValueError, OSError):
            #         pass  # tried to communicate with dead process
            #     except ExecutionTimeLimitExceeded:
            #         logging.info("Killed process for running too long!")
            #         stderr.write("Execution time limit exceeded!")
            #
            #         if evaluator_process:
            #             exit_code = -1
            #             evaluator_process.kill()
            #             call(['docker', 'kill', '{}'.format(eval_container_name)])
            #         if ingestion_process:
            #             ingestion_program_exit_code = -1
            #             ingestion_process.kill()
            #             call(
            #                 ['docker', 'kill', '{}'.format(ingestion_container_name)])
            #         if detailed_result_process:
            #             detailed_result_process.kill()
            #
            #         timed_out = True
            #
            #     signal.alarm(0)
            #
            #     if evaluator_process:
            #         logging.info("Exit Code regular process: %d", exit_code)
            #     if ingestion_process:
            #         logging.info("Exit Code ingestion process: %d",
            #                     ingestion_program_exit_code)
            #         debug_metadata[
            #             'ingestion_program_duration'] = time.time() - ingestion_program_start_time
            #
            #     if detailed_result_process:
            #         detailed_result_process.kill()
            # else:
            #     # let code down below know everything went OK
            #     exit_code = 0
            #     ingestion_program_exit_code = 0

            # Set exit codes to 0 so task is marked as finished
            # if not evaluator_process:
            #     exit_code = 0
            # if not ingestion_process:
            #     ingestion_program_exit_code = 0
            exit_code = 0
            ingestion_program_exit_code = 0
            if detailed_result_process:
                detailed_result_process.kill()

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

        # END FOR

        stdout.close()
        stderr.close()

        logging.info("Saving output files")

        util.put_blob(stdout_url, stdout_file)
        util.put_blob(stderr_url, stderr_file)

        if run_ingestion_program:
            ingestion_stdout.close()
            ingestion_stderr.close()
            util.put_blob(ingestion_program_output_url, ingestion_stdout_file)
            util.put_blob(ingestion_program_stderr_url, ingestion_stderr_file)

        private_dir = os.path.join(output_dir, 'private')
        if os.path.exists(private_dir):
            logging.info("Packing private results...")
            private_output_file = os.path.join(root_dir, 'run', 'private_output.zip')
            shutil.make_archive(os.path.splitext(private_output_file)[0], 'zip',
                                output_dir)
            util.put_blob(private_output_url, private_output_file)
            shutil.rmtree(private_dir, ignore_errors=True)

        # Pack results and send them to Blob storage
        logging.info("Packing results...")
        output_file = os.path.join(root_dir, 'run', 'output.zip')
        shutil.make_archive(os.path.splitext(output_file)[0], 'zip', output_dir)
        util.put_blob(output_url, output_file)

        if detailed_results_url:
            detailed_result_data = open(default_detailed_result_path).read()
            if not detailed_result_data:
                #
                # *LEGACY* detailed result, grabs first *.html it sees -- newer versions use regular path
                # and update in real time
                #

                for root, dirs, files in os.walk(output_dir):
                    # Check if the output folder contain an "html file" and copy the html file as detailed_results.html
                    # traverse root directory, and list directories as dirs and files as files
                    html_found = False
                    if not (html_found):
                        path = root.split('/')
                        for file in files:
                            file_to_upload = os.path.join(root, file)
                            file_ext = os.path.splitext(file_to_upload)[1]
                            if file_ext.lower() == ".html":
                                util.put_blob(detailed_results_url, file_to_upload)
                                html_found = True
                    else:
                        break

        # Save extra metadata
        debug_metadata["end_virtual_memory_usage"] = json.dumps(
            psutil.virtual_memory()._asdict())
        debug_metadata["end_swap_memory_usage"] = json.dumps(
            psutil.swap_memory()._asdict())
        debug_metadata["end_cpu_usage"] = psutil.cpu_percent(interval=None)

        # check if timed out AFTER output files are written! If we exit sooner, no output is written
        if timed_out:
            logging.exception("Run task timed out (task_id=%s).", task_id)
            worker._send_update(task_id, 'failed', secret, extra={
                'metadata': debug_metadata
            })
        elif exit_code != 0 or ingestion_program_exit_code != 0:
            logging.exception("Run task exit code non-zero (task_id=%s).", task_id)
            worker._send_update(task_id, 'failed', secret, extra={
                'traceback': open(stderr_file).read(),
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

        logging.exception("Run task failed (task_id=%s).", task_id)
        worker._send_update(task_id, 'failed', secret, extra={
            'traceback': traceback.format_exc(),
            'metadata': debug_metadata
        })

    # comment out for dev and viewing of raw folder outputs.
    if root_dir is not None and not os.environ.get("DONT_FINALIZE_SUBMISSION"):
        # Try cleaning-up temporary directory
        try:
            os.chdir(current_dir)
            shutil.rmtree(root_dir, ignore_errors=True)
        except:
            logging.exception("Unable to clean-up local folder %s (task_id=%s)",
                              root_dir, task_id)
