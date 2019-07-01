run_aci_celery:
	celery worker -A aci_compute_worker -l info -Q compute-worker -n compute-worker -Ofast -Ofair --concurrency=1