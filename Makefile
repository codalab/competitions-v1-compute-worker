docker_build_scratch:
	docker build --no-cache -t aci_compute_worker .

docker_build:
	docker build -t aci_compute_worker .

docker_debug:
	docker run  -it -- entrypoint='' --network="host" -v ${MOUNT_AZURE}:${MOUNT_AZURE} --env-file .env_sample -v `pwd`/.azure:/root/.azure aci_compute_worker

docker_push: docker_build_scratch
	docker tag aci_compute_worker musinov/aci_compute_worker
	docker push musinov/aci_compute_worker

#if no connection with AFS - use port-forwarding
#ssh -L 8081:$STORAGE_NAME.file.core.windows.net:445 <Azure_VM_USER>@<Azure_IP>
afs_mount:
	mkdir -p ${MOUNT_AZURE}
	sudo mount -t cifs //127.0.0.1/${AZURE_SHARE} ${MOUNT_AZURE} -o rw,vers=3.0,port=8081,username=${STORAGE_NAME},password=${STORAGE_KEY},uid=1000,dir_mode=0777,file_mode=0777,serverino

#Mount AFS before usage
docker_run:
	docker run  --network="host" -v ${MOUNT_AZURE}:${MOUNT_AZURE} --env-file .env_sample -v `pwd`/.azure:/root/.azure aci_compute_worker

run_aci_worker:
	celery worker -A celerymain -l info -Q compute-worker -n compute-worker -Ofast -Ofair --concurrency=1

# run_simple_worker:
# 	celery worker -A worker -l info -Q compute-worker -n compute-worker -Ofast -Ofair --concurrency=1