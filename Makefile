run_aci_celery:
	celery worker -A worker -l info -Q compute-worker -n compute-worker -Ofast -Ofair --concurrency=1