Running
=======

```
docker run --env-file .env \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /tmp/codalab:/tmp/codalab \
    competitions-v1-compute-worker
```


Development
===========

To re-build the image:

```
docker build -t competitions-v1-compute-worker .
```