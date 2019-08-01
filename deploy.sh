#!/bin/bash
WORKERS_NUM=$1
echo "Deploying $WORKERS_NUM workers"
for (( i = 1; i <= $WORKERS_NUM; i++ ))
do
    AZURE_SHARE="worker$i"
    WORKER_FOLDER=$MOUNT_AZURE/$AZURE_SHARE
    sudo mkdir -p $WORKER_FOLDER
    sudo mount -t cifs //$STORAGE_NAME.file.core.windows.net/$AZURE_SHARE $WORKER_FOLDER \
        -o rw,vers=3.0,port=445,username=$STORAGE_NAME,password=$STORAGE_KEY,uid=1000,dir_mode=0777,$
    docker run -d --rm  --name=$AZURE_SHARE --network="host" \
        -v $WORKER_FOLDER:/tmp/codalab \
        --env AFS_SHARE=$AZURE_SHARE \
        --env-file .env_sample \
        -v /home/imusinov/.azure:/root/.azure aci_compute_worker
    echo "$AZURE_SHARE was deployed"
done

