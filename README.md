Running
=======

### If you want to run everything in one line:

*Note: this will make a `/tmp/codalab` directory*

```
mkdir -p /tmp/codalab && docker run \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /tmp/codalab:/tmp/codalab \
    --env BROKER_URL=<queue broker url> \
    ckcollab/competitions-v1-compute-worker:latest
```


### If you want to run using `.env` configuration:

Edit `.env_sample` and save it as `.env`

Make sure the temp directory you select is created and pass it in this command

```
docker run \
    --env-file .env \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v <SUBMISSION TEMP DIRECTORY>:<SUBMISSION TEMP DIRECTORY> \
    ckcollab/competitions-v1-compute-worker:latest
```


Development
===========

To re-build the image:

```
docker build -t competitions-v1-compute-worker .
```

Updating the image

```
docker build -t ckcollab/competitions-v1-compute-worker:latest .
docker push ckcollab/competitions-v1-compute-worker
```
