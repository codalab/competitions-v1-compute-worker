#!/usr/bin/env bash
mkdir -p /tmp/codalab

docker run --privileged \
            --network="host" \
            -v /tmp/codalab:/tmp/codalab \
            --env BROKER_URL=pyamqp://guest:guest@0.0.0.0:5671 \
            --env BROKER_USE_SSL=True \
            --env WORKER_CONCURRENCY=1 \
            --env SUBMISSION_TEMP_DIR=/tmp/codalab \
            --env WORKER=aci_worker \
            --env QUEUE=compute-worker \
            -m 6g \
            -d  \
            compute-worker-aci