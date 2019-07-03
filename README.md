Running
=======

### If you want to run everything in one line:

*Note: this will make a `/tmp/codalab` directory*

```
mkdir -p /tmp/codalab && nvidia-docker run \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /var/lib/nvidia-docker/nvidia-docker.sock:/var/lib/nvidia-docker/nvidia-docker.sock \
    -v - ./var/data/worker/:/worker/registration \
    -v /tmp/codalab:/tmp/codalab \
    -d \
    --name compute_worker \
    --env BROKER_URL=<queue broker url> \
    --restart unless-stopped \
    --log-opt max-size=50m \
    --log-opt max-file=3 \
    codalab/competitions-v1-nvidia-worker:latest
```


### If you want to run using `.env` configuration:

Edit `.env_sample` and save it as `.env`

Make sure the temp directory you select is created and pass it in this command

```
nvidia-docker run \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /var/lib/nvidia-docker/nvidia-docker.sock:/var/lib/nvidia-docker/nvidia-docker.sock \
    -v - ./var/data/worker/:/worker/registration \
    -v /tmp/codalab:/tmp/codalab \
    -d \
    --name compute_worker \
    --env-file .env \
    --restart unless-stopped \
    --log-opt max-size=50m \
    --log-opt max-file=3 \
    codalab/competitions-v1-nvidia-worker:latest
```

### To get output of the worker

```
$ nvidia-docker logs -f compute_worker
```

### To stop the worker

```
$ nvidia-docker kill compute_worker
```


Development
===========

To re-build the image:

```
docker build -t competitions-v1-nvidia-worker .
```

Updating the image

```
docker build -t codalab/competitions-v1-nvidia-worker:latest .
docker push codalab/competitions-v1-nvidia-worker:latest
```


Special env flags
=================


### DONT_FINALIZE_SUBMISSION

Sometimes it may be useful to pause the compute worker and return instead of finishing a submission. This leaves the
submission in a state where it hasn't been cleaned up yet and you can attempt to re-run it manually.

